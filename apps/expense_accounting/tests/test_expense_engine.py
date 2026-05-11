from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase

from apps.ledgers.models import Account, Currency, FiscalPeriod
from apps.ledgers.seed import seed_default_chart_of_accounts
from apps.ledgers.utils.ledger import calculate_trial_balance

from apps.expense_accounting.constants import ZERO
from apps.expense_accounting.exceptions import (
    BudgetExceededError,
    ExpenseApprovalError,
    ExpenseStatusError,
)
from apps.expense_accounting.models import (
    ExpenseApproval,
    ExpenseBudget,
    ExpenseCategory,
    ExpenseTransaction,
    PrepaidExpenseSchedule,
)
from apps.expense_accounting.services.expense_approval_service import (
    approve_expense,
    determine_approval_level,
    reject_expense,
)
from apps.expense_accounting.services.expense_budget_service import (
    check_budget_availability,
    consume_budget,
    generate_budget_variance,
    release_budget,
)
from apps.expense_accounting.services.expense_posting_service import (
    create_expense,
    pay_expense,
    post_expense,
    reverse_expense,
    submit_expense,
)
from apps.expense_accounting.services.expense_tax_service import (
    calculate_input_vat,
    calculate_withholding_tax,
    split_tax_amounts,
)
from apps.expense_accounting.services.prepaid_expense_service import (
    amortize_prepaid_expense,
    create_prepaid_schedule,
)
from apps.expense_accounting.services.reimbursement_service import reimburse_employee


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _open_period(start=date(2026, 5, 1), end=date(2026, 5, 31)):
    period, _ = FiscalPeriod.objects.get_or_create(
        name=f"{start.isoformat()}–{end.isoformat()}",
        defaults={"start_date": start, "end_date": end, "is_closed": False},
    )
    return period


def _category(name="Utilities", expense_type="operational"):
    expense_account = Account.objects.get(category="operating_expenses")
    credit_account = Account.objects.get(category="accounts_payable")
    cat, _ = ExpenseCategory.objects.get_or_create(
        name=name,
        defaults={
            "expense_type": expense_type,
            "default_expense_account": expense_account,
            "default_credit_account": credit_account,
            "requires_approval": True,
        },
    )
    return cat


def _create_draft(
    ref="EXP-001",
    amount=Decimal("200000"),
    expense_type="operational",
    currency_code="UGX",
    tax_amount=ZERO,
):
    category = _category(name=f"Cat-{expense_type}-{ref}", expense_type=expense_type)
    return create_expense(
        reference=ref,
        expense_category_id=category.id,
        vendor="ACME Corp",
        amount=amount,
        tax_amount=tax_amount,
        description=f"Test expense {ref}",
        expense_date=date(2026, 5, 10),
        created_by_id=uuid4(),
        currency_code=currency_code,
    )


class ExpensePostingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_default_chart_of_accounts(currency="USD")
        _open_period()

    # --- creation -----------------------------------------------------------

    def test_create_expense_creates_draft(self):
        expense = _create_draft("EXP-CREATE-001")
        self.assertEqual(expense.status, ExpenseTransaction.Status.DRAFT)
        self.assertGreater(expense.base_amount, ZERO)

    def test_create_expense_creates_default_line(self):
        expense = _create_draft("EXP-LINE-001")
        self.assertEqual(expense.lines.count(), 1)
        self.assertEqual(expense.lines.first().base_amount, expense.base_amount)

    # --- submit → approve → post -------------------------------------------

    def test_submit_routes_for_approval(self):
        expense = _create_draft("EXP-SUB-001", amount=Decimal("100000"))
        submitted = submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        self.assertEqual(submitted.status, ExpenseTransaction.Status.SUBMITTED)
        self.assertTrue(submitted.approvals.filter(status=ExpenseApproval.Status.PENDING).exists())

    def test_approve_marks_approved(self):
        expense = _create_draft("EXP-APR-001", amount=Decimal("100000"))
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        approved = approve_expense(expense_id=expense.id, approver_id=uuid4(), remarks="OK")
        self.assertEqual(approved.status, ExpenseTransaction.Status.APPROVED)
        self.assertEqual(approved.approval_status, ExpenseTransaction.ApprovalStatus.APPROVED)

    def test_post_expense_creates_balanced_journal(self):
        expense = _create_draft("EXP-POST-001", amount=Decimal("300000"))
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        approve_expense(expense_id=expense.id, approver_id=uuid4())
        posted = post_expense(expense_id=expense.id, posted_by_id=uuid4(), enforce_budget=False)
        self.assertEqual(posted.status, ExpenseTransaction.Status.POSTED)
        self.assertIsNotNone(posted.journal_entry_id)
        tb = calculate_trial_balance(date(2026, 5, 31))
        self.assertEqual(tb["difference"], Decimal("0.00"))

    def test_cannot_post_draft_expense(self):
        expense = _create_draft("EXP-NOPOST-001")
        with self.assertRaises(ExpenseStatusError):
            post_expense(expense_id=expense.id, posted_by_id=uuid4(), enforce_budget=False)

    # --- pay ----------------------------------------------------------------

    def test_pay_expense_creates_balanced_journal(self):
        expense = _create_draft("EXP-PAY-001", amount=Decimal("150000"))
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        approve_expense(expense_id=expense.id, approver_id=uuid4())
        post_expense(expense_id=expense.id, posted_by_id=uuid4(), enforce_budget=False)
        cash = Account.objects.get(category="cash_and_cash_equivalent_control")
        pay_expense(expense_id=expense.id, payment_date=date(2026, 5, 15), cash_account_id=cash.id)
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseTransaction.Status.PAID)
        tb = calculate_trial_balance(date(2026, 5, 31))
        self.assertEqual(tb["difference"], Decimal("0.00"))

    # --- reversal -----------------------------------------------------------

    def test_reverse_expense_nets_to_zero(self):
        expense = _create_draft("EXP-REV-001", amount=Decimal("500000"))
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        approve_expense(expense_id=expense.id, approver_id=uuid4())
        post_expense(expense_id=expense.id, posted_by_id=uuid4(), enforce_budget=False)

        tb_before = calculate_trial_balance(date(2026, 5, 31))["difference"]
        reverse_expense(expense_id=expense.id, reversal_date=date(2026, 5, 20), reason="test reversal")
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseTransaction.Status.REVERSED)
        self.assertEqual(tb_before, Decimal("0.00"))

    def test_cannot_reverse_non_posted(self):
        expense = _create_draft("EXP-NOREV-001")
        with self.assertRaises(ExpenseStatusError):
            reverse_expense(expense_id=expense.id, reversal_date=date(2026, 5, 20))


class ExpenseVATTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_default_chart_of_accounts(currency="USD")
        _open_period()

    def test_supplier_expense_with_vat_posts_three_lines(self):
        expense = _create_draft("EXP-VAT-001", amount=Decimal("200000"), tax_amount=Decimal("36000"), expense_type="supplier")
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        approve_expense(expense_id=expense.id, approver_id=uuid4())
        posted = post_expense(expense_id=expense.id, posted_by_id=uuid4(), enforce_budget=False)
        # DR Expense + DR VAT Input + CR AP = 3 lines
        self.assertEqual(posted.journal_entry.lines.count(), 3)
        tb = calculate_trial_balance(date(2026, 5, 31))
        self.assertEqual(tb["difference"], Decimal("0.00"))

    def test_calculate_input_vat(self):
        vat = calculate_input_vat(net_amount=Decimal("200000"), vat_rate=Decimal("0.18"))
        self.assertEqual(vat, Decimal("36000.00"))

    def test_split_inclusive_tax(self):
        net, tax = split_tax_amounts(amount=Decimal("236000"), tax_rate=Decimal("0.18"), tax_inclusive=True)
        self.assertAlmostEqual(float(net + tax), 236000.0, places=1)
        self.assertGreater(tax, ZERO)

    def test_withholding_tax_calculation(self):
        wht = calculate_withholding_tax(gross_amount=Decimal("500000"), wht_rate=Decimal("0.06"))
        self.assertEqual(wht, Decimal("30000.00"))


class ExpenseApprovalWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_default_chart_of_accounts()
        _open_period()

    def test_low_amount_requires_manager_level(self):
        level, label = determine_approval_level(base_amount_ugx=Decimal("200000"))
        self.assertEqual(level, 1)
        self.assertEqual(label, "manager")

    def test_mid_amount_requires_finance_level(self):
        level, label = determine_approval_level(base_amount_ugx=Decimal("2000000"))
        self.assertEqual(level, 2)
        self.assertEqual(label, "finance")

    def test_high_amount_requires_cfo_level(self):
        level, label = determine_approval_level(base_amount_ugx=Decimal("10000000"))
        self.assertEqual(level, 3)
        self.assertEqual(label, "cfo")

    def test_reject_expense_sets_rejected_status(self):
        expense = _create_draft("EXP-REJECT-001", amount=Decimal("100000"))
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        rejected = reject_expense(expense_id=expense.id, approver_id=uuid4(), remarks="No budget")
        self.assertEqual(rejected.status, ExpenseTransaction.Status.REJECTED)
        self.assertEqual(rejected.approval_status, ExpenseTransaction.ApprovalStatus.REJECTED)

    def test_double_approval_raises(self):
        expense = _create_draft("EXP-DBLAP-001", amount=Decimal("100000"))
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        approve_expense(expense_id=expense.id, approver_id=uuid4())
        with self.assertRaises(ExpenseStatusError):
            approve_expense(expense_id=expense.id, approver_id=uuid4())


class ExpenseBudgetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_default_chart_of_accounts()
        _open_period()

    def _period_id(self):
        from apps.ledgers.models import FiscalPeriod
        return FiscalPeriod.objects.get(name="2026-05-01–2026-05-31").id

    def test_budget_consumption_updates_remaining(self):
        cat = _category("BudgCat")
        period_id = self._period_id()
        budget = ExpenseBudget.objects.create(
            fiscal_period_id=period_id,
            department="Finance",
            expense_category=cat,
            budget_amount=Decimal("1000000"),
            created_by=uuid4(),
        )
        consume_budget(
            fiscal_period_id=period_id,
            amount_ugx=Decimal("200000"),
            department="Finance",
            expense_category_id=cat.id,
        )
        budget.refresh_from_db()
        self.assertEqual(budget.consumed_amount, Decimal("200000.00"))
        self.assertEqual(budget.remaining_amount, Decimal("800000.00"))

    def test_budget_exceeded_raises(self):
        cat = _category("BudgCat2")
        period_id = self._period_id()
        ExpenseBudget.objects.create(
            fiscal_period_id=period_id,
            department="IT",
            expense_category=cat,
            budget_amount=Decimal("100000"),
            created_by=uuid4(),
        )
        with self.assertRaises(BudgetExceededError):
            check_budget_availability(
                fiscal_period_id=period_id,
                amount_ugx=Decimal("200000"),
                department="IT",
                expense_category_id=cat.id,
                raise_on_exceeded=True,
            )

    def test_release_budget_on_reversal(self):
        cat = _category("BudgCat3")
        period_id = self._period_id()
        ExpenseBudget.objects.create(
            fiscal_period_id=period_id,
            department="HR",
            expense_category=cat,
            budget_amount=Decimal("500000"),
            consumed_amount=Decimal("300000"),
            created_by=uuid4(),
        )
        release_budget(
            fiscal_period_id=period_id,
            amount_ugx=Decimal("300000"),
            department="HR",
            expense_category_id=cat.id,
        )
        budget = ExpenseBudget.objects.get(department="HR", expense_category=cat)
        self.assertEqual(budget.consumed_amount, ZERO)

    def test_generate_budget_variance(self):
        period_id = self._period_id()
        variances = generate_budget_variance(fiscal_period_id=period_id)
        self.assertIsInstance(variances, list)


class PrepaidExpenseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_default_chart_of_accounts()
        _open_period()

    def _make_prepaid_expense(self, ref="PRE-001"):
        cat, _ = ExpenseCategory.objects.get_or_create(
            name=f"Insurance-{ref}",
            defaults={
                "expense_type": "prepaid",
                "default_expense_account": Account.objects.get(category="operating_expenses"),
                "default_credit_account": Account.objects.get(category="accounts_payable"),
                "requires_approval": False,
            },
        )
        expense = create_expense(
            reference=ref,
            expense_category_id=cat.id,
            vendor="Insurance Co",
            amount=Decimal("1200000"),
            description="Annual insurance",
            expense_date=date(2026, 5, 1),
            created_by_id=uuid4(),
        )
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        return expense

    def test_create_prepaid_schedule(self):
        expense = self._make_prepaid_expense("PRE-SCHED-001")
        prepaid_account = Account.objects.get(category="prepaid_expenses")
        credit_account = Account.objects.get(category="accounts_payable")
        schedule = create_prepaid_schedule(
            expense=expense,
            start_date=date(2026, 5, 1),
            end_date=date(2027, 4, 30),
            prepaid_account=prepaid_account,
            credit_account=credit_account,
        )
        self.assertEqual(schedule.total_months, 12)
        self.assertEqual(schedule.status, PrepaidExpenseSchedule.Status.ACTIVE)
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseTransaction.Status.POSTED)
        tb = calculate_trial_balance(date(2026, 5, 31))
        self.assertEqual(tb["difference"], Decimal("0.00"))

    def test_amortization_reduces_balance(self):
        expense = self._make_prepaid_expense("PRE-AMORT-001")
        prepaid_account = Account.objects.get(category="prepaid_expenses")
        ap_account = Account.objects.get(category="accounts_payable")
        schedule = create_prepaid_schedule(
            expense=expense,
            start_date=date(2026, 5, 1),
            end_date=date(2027, 4, 30),
            prepaid_account=prepaid_account,
            credit_account=ap_account,
        )
        expense_account = Account.objects.get(category="operating_expenses")
        result = amortize_prepaid_expense(
            schedule=schedule,
            amortization_date=date(2026, 5, 31),
            expense_account=expense_account,
            prepaid_account=prepaid_account,
        )
        schedule.refresh_from_db()
        self.assertEqual(schedule.amortizations_posted, 1)
        self.assertLess(schedule.remaining_base_balance, expense.base_amount)
        self.assertEqual(result["period"], 1)

    def test_twelve_amortizations_complete_schedule(self):
        expense = self._make_prepaid_expense("PRE-FULL-001")
        _open_period(date(2026, 6, 1), date(2027, 4, 30))
        prepaid_account = Account.objects.get(category="prepaid_expenses")
        ap_account = Account.objects.get(category="accounts_payable")
        expense_account = Account.objects.get(category="operating_expenses")
        schedule = create_prepaid_schedule(
            expense=expense,
            start_date=date(2026, 5, 1),
            end_date=date(2027, 4, 30),
            prepaid_account=prepaid_account,
            credit_account=ap_account,
        )
        from apps.expense_accounting.utils.expense_calculations import add_months
        for i in range(12):
            schedule.refresh_from_db()
            amort_date = add_months(date(2026, 5, 31), i)
            amortize_prepaid_expense(
                schedule=schedule,
                amortization_date=amort_date,
                expense_account=expense_account,
                prepaid_account=prepaid_account,
            )
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, PrepaidExpenseSchedule.Status.COMPLETED)
        self.assertEqual(schedule.remaining_base_balance, ZERO)


class EmployeeReimbursementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_default_chart_of_accounts()
        _open_period()

    def test_full_reimbursement_lifecycle(self):
        employee_id = uuid4()
        cat, _ = ExpenseCategory.objects.get_or_create(
            name="Travel-Reimb",
            defaults={
                "expense_type": "employee_reimbursement",
                "default_expense_account": Account.objects.get(category="operating_expenses"),
                "default_credit_account": Account.objects.get(category="employee_reimbursement_liability"),
                "requires_approval": True,
            },
        )
        expense = create_expense(
            reference="REIMB-001",
            expense_category_id=cat.id,
            employee=employee_id,
            amount=Decimal("350000"),
            description="Field trip fuel",
            expense_date=date(2026, 5, 5),
            created_by_id=uuid4(),
        )
        submit_expense(expense_id=expense.id, submitted_by_id=employee_id)
        approve_expense(expense_id=expense.id, approver_id=uuid4())
        post_expense(expense_id=expense.id, posted_by_id=uuid4(), enforce_budget=False)

        cash = Account.objects.get(category="cash_and_cash_equivalent_control")
        reimb_account = Account.objects.get(category="employee_reimbursement_liability")
        reimburse_employee(
            expense=expense,
            payment_date=date(2026, 5, 20),
            cash_account=cash,
            reimbursement_liability_account=reimb_account,
        )
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseTransaction.Status.PAID)
        tb = calculate_trial_balance(date(2026, 5, 31))
        self.assertEqual(tb["difference"], Decimal("0.00"))


class CapitalExpenseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_default_chart_of_accounts()
        _open_period()

    def test_capital_expense_debits_fixed_assets(self):
        cat, _ = ExpenseCategory.objects.get_or_create(
            name="Equipment Purchase",
            defaults={
                "expense_type": "capital",
                "default_expense_account": Account.objects.get(category="fixed_assets"),
                "default_credit_account": Account.objects.get(category="accounts_payable"),
                "requires_approval": True,
                "is_capitalizable": True,
            },
        )
        expense = create_expense(
            reference="CAP-001",
            expense_category_id=cat.id,
            vendor="Equipment Supplier",
            amount=Decimal("5000000"),
            description="Server purchase",
            expense_date=date(2026, 5, 8),
            created_by_id=uuid4(),
        )
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        approve_expense(expense_id=expense.id, approver_id=uuid4())
        posted = post_expense(expense_id=expense.id, posted_by_id=uuid4(), enforce_budget=False)
        # Journal should debit Fixed Assets, not Expense
        lines = list(posted.journal_entry.lines.all())
        debit_accounts = [l.account.category for l in lines if l.debit_base > 0]
        self.assertIn("fixed_assets", debit_accounts)
        tb = calculate_trial_balance(date(2026, 5, 31))
        self.assertEqual(tb["difference"], Decimal("0.00"))


class MultiCurrencyExpenseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_default_chart_of_accounts(currency="USD")
        _open_period()
        from apps.ledgers.models import ExchangeRate
        ugx = Currency.objects.get(code="UGX")
        usd = Currency.objects.get(code="USD")
        ExchangeRate.objects.get_or_create(
            from_currency=usd,
            to_currency=ugx,
            date=date(2026, 5, 10),
            defaults={"rate": Decimal("3800.000000"), "source": "test"},
        )

    def test_usd_expense_stores_ugx_base(self):
        expense = _create_draft("EXP-USD-001", amount=Decimal("100.00"), currency_code="USD")
        self.assertGreater(expense.base_amount, Decimal("100"))  # base must be in UGX
        self.assertEqual(expense.currency.code, "USD")

    def test_usd_expense_journal_balances_in_ugx(self):
        expense = _create_draft("EXP-USD-POST-001", amount=Decimal("50.00"), currency_code="USD")
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        approve_expense(expense_id=expense.id, approver_id=uuid4())
        post_expense(expense_id=expense.id, posted_by_id=uuid4(), enforce_budget=False)
        tb = calculate_trial_balance(date(2026, 5, 31))
        self.assertEqual(tb["difference"], Decimal("0.00"))


class AccrualExpenseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_default_chart_of_accounts()
        _open_period()
        _open_period(date(2026, 6, 1), date(2026, 6, 30))

    def test_accrual_and_reversal_net_zero(self):
        cat, _ = ExpenseCategory.objects.get_or_create(
            name="Accrued Utilities",
            defaults={
                "expense_type": "accrual",
                "default_expense_account": Account.objects.get(category="operating_expenses"),
                "default_credit_account": Account.objects.get(category="accrued_expense_provision"),
                "requires_approval": False,
            },
        )
        expense = create_expense(
            reference="ACCR-001",
            expense_category_id=cat.id,
            amount=Decimal("400000"),
            description="May electricity accrual",
            expense_date=date(2026, 5, 31),
            created_by_id=uuid4(),
        )
        submit_expense(expense_id=expense.id, submitted_by_id=uuid4())
        post_expense(expense_id=expense.id, posted_by_id=uuid4(), enforce_budget=False)
        reverse_expense(expense_id=expense.id, reversal_date=date(2026, 6, 1), reason="Period-end reversal")
        tb = calculate_trial_balance(date(2026, 6, 30))
        self.assertEqual(tb["difference"], Decimal("0.00"))
