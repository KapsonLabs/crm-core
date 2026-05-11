from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.expense_accounting.constants import (
    IK_ACCRUAL_EXPENSE,
    IK_EXPENSE,
    IK_EXPENSE_PAYMENT,
    IK_EXPENSE_REVERSAL,
    SOURCE_MODULE,
    ZERO,
)
from apps.expense_accounting.exceptions import ExpenseConfigurationError, ExpenseStatusError
from apps.expense_accounting.models import ExpenseCategory, ExpenseLine, ExpenseTransaction
from apps.expense_accounting.services.expense_approval_service import determine_approval_level, route_for_approval
from apps.expense_accounting.services.expense_budget_service import check_budget_availability, consume_budget, release_budget
from apps.expense_accounting.utils.expense_calculations import convert_to_base, round_currency
from apps.ledgers.models import Account
from apps.ledgers.services.audit_service import emit_audit_log
from apps.ledgers.services.helpers import create_and_post_journal, get_configured_account
from apps.ledgers.services.journal_service import reverse_journal_entry
from apps.ledgers.services.types import JournalLineInput
from apps.ledgers.utils.currency import get_exchange_rate
from apps.ledgers.utils.periods import ensure_date_in_open_period


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_account(account_id: UUID | None, fallback_key: str, branch: UUID | None) -> Account:
    if account_id:
        return Account.objects.get(id=account_id)
    return get_configured_account(fallback_key, branch)


def _resolve_exchange_rate(currency_code: str, rate_date: date, branch: UUID | None) -> Decimal:
    from apps.ledgers.constants import DEFAULT_CURRENCY
    if currency_code == DEFAULT_CURRENCY:
        return Decimal("1.000000")
    return get_exchange_rate(
        from_currency_code=currency_code,
        to_currency_code=DEFAULT_CURRENCY,
        rate_date=rate_date,
    )


# ---------------------------------------------------------------------------
# Lifecycle functions
# ---------------------------------------------------------------------------

@transaction.atomic
def create_expense(
    *,
    reference: str,
    expense_category_id: UUID,
    vendor: str = "",
    employee: UUID | None = None,
    branch: UUID | None = None,
    department: str = "",
    project: str = "",
    cost_center: str = "",
    currency_code: str = "UGX",
    amount: Decimal,
    tax_amount: Decimal = ZERO,
    description: str,
    expense_date: date,
    created_by_id: UUID,
    notes: str = "",
    lines: list[dict] | None = None,
) -> ExpenseTransaction:
    """Create a new draft expense transaction.

    Args:
        lines: Optional list of line-level allocations. Each dict:
            account_id, amount, tax_amount, department, project, cost_center, description.
            If omitted the category's default_expense_account is used as a single line.
    """
    from apps.ledgers.models import Currency

    category = ExpenseCategory.objects.select_related(
        "default_expense_account", "default_credit_account"
    ).get(id=expense_category_id)

    if category.requires_project and not project:
        raise ExpenseConfigurationError(f"Category '{category.name}' requires a project.")
    if category.requires_department and not department:
        raise ExpenseConfigurationError(f"Category '{category.name}' requires a department.")

    currency = Currency.objects.get(code=currency_code)
    exchange_rate = _resolve_exchange_rate(currency_code, expense_date, branch)
    base_amount = convert_to_base(amount, exchange_rate)
    tax_base_amount = convert_to_base(tax_amount, exchange_rate)

    expense = ExpenseTransaction.objects.create(
        reference=reference,
        expense_category=category,
        vendor=vendor,
        employee=employee,
        branch=branch,
        department=department,
        project=project,
        cost_center=cost_center,
        currency=currency,
        exchange_rate=exchange_rate,
        amount=amount,
        base_amount=base_amount,
        tax_amount=tax_amount,
        tax_base_amount=tax_base_amount,
        description=description,
        expense_date=expense_date,
        status=ExpenseTransaction.Status.DRAFT,
        approval_status=(
            ExpenseTransaction.ApprovalStatus.NOT_REQUIRED
            if not category.requires_approval
            else ExpenseTransaction.ApprovalStatus.PENDING
        ),
        payment_status=ExpenseTransaction.PaymentStatus.UNPAID,
        created_by=created_by_id,
        notes=notes,
    )

    if lines:
        for i, line in enumerate(lines):
            ExpenseLine.objects.create(
                expense_transaction=expense,
                expense_account_id=line["account_id"],
                amount=Decimal(str(line.get("amount", amount))),
                base_amount=convert_to_base(Decimal(str(line.get("amount", amount))), exchange_rate),
                tax_amount=Decimal(str(line.get("tax_amount", ZERO))),
                tax_base_amount=convert_to_base(Decimal(str(line.get("tax_amount", ZERO))), exchange_rate),
                department=line.get("department", department),
                project=line.get("project", project),
                cost_center=line.get("cost_center", cost_center),
                description=line.get("description", description),
                order=i,
            )
    elif category.default_expense_account_id:
        ExpenseLine.objects.create(
            expense_transaction=expense,
            expense_account=category.default_expense_account,
            amount=amount,
            base_amount=base_amount,
            tax_amount=tax_amount,
            tax_base_amount=tax_base_amount,
            department=department,
            project=project,
            cost_center=cost_center,
            description=description,
            order=0,
        )

    emit_audit_log(
        event_type="expense.created",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=branch,
        performed_by_id=created_by_id,
        payload={"reference": reference, "amount_ugx": str(base_amount), "category": category.name},
    )
    return expense


@transaction.atomic
def submit_expense(*, expense_id: UUID, submitted_by_id: UUID) -> ExpenseTransaction:
    """Submit a draft expense for approval."""
    expense = ExpenseTransaction.objects.select_for_update().get(id=expense_id)
    if expense.status != ExpenseTransaction.Status.DRAFT:
        raise ExpenseStatusError(f"Cannot submit expense in status '{expense.status}'.")

    expense.status = ExpenseTransaction.Status.SUBMITTED
    expense.save(update_fields=["status", "updated_at"])

    category = expense.expense_category
    needs_approval = category.requires_approval and (
        category.approval_required_above is None
        or expense.base_amount > category.approval_required_above
    )
    if needs_approval:
        route_for_approval(expense=expense)
    else:
        expense.approval_status = ExpenseTransaction.ApprovalStatus.NOT_REQUIRED
        expense.status = ExpenseTransaction.Status.APPROVED
        expense.save(update_fields=["approval_status", "status", "updated_at"])

    emit_audit_log(
        event_type="expense.submitted",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=expense.branch,
        performed_by_id=submitted_by_id,
        payload={"needs_approval": needs_approval},
    )
    return expense


@transaction.atomic
def post_expense(
    *,
    expense_id: UUID,
    posted_by_id: UUID | None = None,
    credit_account_id: UUID | None = None,
    fiscal_period_id: UUID | None = None,
    enforce_budget: bool = True,
) -> ExpenseTransaction:
    """Post an approved expense to the general ledger.

    Selects the journal pattern based on expense_type:

    operational / supplier:
        DR Expense (+ DR VAT Input if tax_amount > 0)
        CR Accounts Payable

    employee_reimbursement:
        DR Expense
        CR Employee Reimbursement Liability

    capital:
        DR Fixed Asset
        CR Accounts Payable / Cash

    accrual:
        DR Expense
        CR Accrued Expense Provision

    prepaid / deferred:
        Handled by prepaid_expense_service.create_prepaid_schedule() instead.
    """
    expense = ExpenseTransaction.objects.select_for_update().select_related(
        "expense_category__default_expense_account",
        "expense_category__default_credit_account",
        "currency",
    ).get(id=expense_id)

    if expense.status != ExpenseTransaction.Status.APPROVED:
        raise ExpenseStatusError(f"Cannot post expense in status '{expense.status}'.")

    category = expense.expense_category
    if category.expense_type in ("prepaid", "deferred"):
        raise ExpenseStatusError(
            "Prepaid/deferred expenses must be posted via prepaid_expense_service.create_prepaid_schedule()."
        )

    ensure_date_in_open_period(posting_date=expense.expense_date, branch=expense.branch)

    if enforce_budget and fiscal_period_id:
        check_budget_availability(
            fiscal_period_id=fiscal_period_id,
            amount_ugx=expense.base_amount,
            department=expense.department,
            branch=expense.branch,
            project=expense.project,
            expense_category_id=category.id,
            raise_on_exceeded=True,
        )

    journal = _build_and_post_journal(expense=expense, credit_account_id=credit_account_id)

    if enforce_budget and fiscal_period_id:
        consume_budget(
            fiscal_period_id=fiscal_period_id,
            amount_ugx=expense.base_amount,
            department=expense.department,
            branch=expense.branch,
            project=expense.project,
            expense_category_id=category.id,
        )

    expense.journal_entry = journal
    expense.status = ExpenseTransaction.Status.POSTED
    expense.posted_at = timezone.now()
    expense.save(update_fields=["journal_entry", "status", "posted_at", "updated_at"])

    emit_audit_log(
        event_type="expense.posted",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=expense.branch,
        performed_by_id=posted_by_id,
        payload={"journal_id": str(journal.id), "amount_ugx": str(expense.base_amount)},
    )
    return expense


def _build_and_post_journal(
    *,
    expense: ExpenseTransaction,
    credit_account_id: UUID | None,
):
    category = expense.expense_category
    currency_code = expense.currency.code
    exchange_rate = expense.exchange_rate
    branch = expense.branch

    def _line(account_id, debit_foreign=ZERO, credit_foreign=ZERO, debit_base=ZERO, credit_base=ZERO, party_type="", party_id=""):
        return JournalLineInput(
            account_id=account_id,
            debit_foreign=debit_foreign,
            credit_foreign=credit_foreign,
            debit_base=debit_base,
            credit_base=credit_base,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            description=expense.description,
            branch=branch,
            party_type=party_type,
            party_id=party_id,
        )

    expense_account = category.default_expense_account or _get_account(None, "operating_expenses", branch)

    if category.expense_type == "capital":
        asset_account = _get_account(None, "fixed_assets", branch)
        credit_account = _get_account(credit_account_id, "accounts_payable", branch)
        lines = [
            _line(asset_account.id, debit_foreign=expense.amount, debit_base=expense.base_amount, party_type="supplier", party_id=expense.vendor),
            _line(credit_account.id, credit_foreign=expense.gross_amount, credit_base=expense.gross_base_amount, party_type="supplier", party_id=expense.vendor),
        ]
        journal_type = "capital_expense"

    elif category.expense_type == "employee_reimbursement":
        reimb_account = _get_account(credit_account_id, "employee_reimbursement_liability", branch)
        lines = [
            _line(expense_account.id, debit_foreign=expense.amount, debit_base=expense.base_amount, party_type="employee", party_id=str(expense.employee or "")),
            _line(reimb_account.id, credit_foreign=expense.amount, credit_base=expense.base_amount, party_type="employee", party_id=str(expense.employee or "")),
        ]
        journal_type = "employee_reimbursement"

    elif category.expense_type == "accrual":
        accrual_account = _get_account(credit_account_id, "accrued_expense_provision", branch)
        lines = [
            _line(expense_account.id, debit_foreign=expense.amount, debit_base=expense.base_amount),
            _line(accrual_account.id, credit_foreign=expense.amount, credit_base=expense.base_amount),
        ]
        journal_type = "accrued_expense"

    elif category.expense_type == "corporate_card":
        card_clearing = _get_account(credit_account_id, "corporate_card_clearing", branch)
        lines = [
            _line(expense_account.id, debit_foreign=expense.amount, debit_base=expense.base_amount, party_type="employee", party_id=str(expense.employee or "")),
            _line(card_clearing.id, credit_foreign=expense.amount, credit_base=expense.base_amount, party_type="employee", party_id=str(expense.employee or "")),
        ]
        journal_type = "corporate_card_expense"

    else:
        # operational / supplier
        payable_account = _get_account(credit_account_id, "accounts_payable", branch)
        gross_foreign = expense.gross_amount
        gross_base = expense.gross_base_amount
        lines = [
            _line(expense_account.id, debit_foreign=expense.amount, debit_base=expense.base_amount, party_type="supplier", party_id=expense.vendor),
        ]
        if expense.tax_amount > ZERO:
            vat_account = _get_account(None, "vat_input_control", branch)
            lines.append(_line(vat_account.id, debit_foreign=expense.tax_amount, debit_base=expense.tax_base_amount))
        lines.append(
            _line(payable_account.id, credit_foreign=gross_foreign, credit_base=gross_base, party_type="supplier", party_id=expense.vendor)
        )
        journal_type = "supplier_expense"

    return create_and_post_journal(
        reference=f"EXP-{expense.reference}",
        journal_type=journal_type,
        posting_date=expense.expense_date,
        description=expense.description,
        source_module=SOURCE_MODULE,
        source_id=str(expense.id),
        branch=branch,
        created_by_id=expense.created_by,
        idempotency_key=f"{IK_EXPENSE}:{expense.id}",
        transaction_currency_code=currency_code,
        lines=lines,
    )


@transaction.atomic
def pay_expense(
    *,
    expense_id: UUID,
    payment_date: date,
    cash_account_id: UUID,
    paid_by_id: UUID | None = None,
) -> dict:
    """Settle a posted supplier or operational expense.

    Posting:
        DR Accounts Payable / Accrued Expense
        CR Cash / Bank
    """
    expense = ExpenseTransaction.objects.select_for_update().select_related(
        "expense_category", "currency"
    ).get(id=expense_id)

    if expense.status != ExpenseTransaction.Status.POSTED:
        raise ExpenseStatusError("Only POSTED expenses can be paid.")
    if expense.payment_status == ExpenseTransaction.PaymentStatus.PAID:
        raise ExpenseStatusError("Expense already paid.")

    ensure_date_in_open_period(posting_date=payment_date, branch=expense.branch)

    category = expense.expense_category
    if category.expense_type == "accrual":
        debit_account = _get_account(None, "accrued_expense_provision", expense.branch)
    else:
        debit_account = _get_account(None, "accounts_payable", expense.branch)
    cash_account = Account.objects.get(id=cash_account_id)

    journal = create_and_post_journal(
        reference=f"EXP-PAY-{expense.reference}",
        journal_type="expense_payment",
        posting_date=payment_date,
        description=f"Payment — {expense.description}",
        source_module=SOURCE_MODULE,
        source_id=str(expense.id),
        branch=expense.branch,
        created_by_id=paid_by_id,
        idempotency_key=f"{IK_EXPENSE_PAYMENT}:{expense.id}",
        transaction_currency_code=expense.currency.code,
        lines=[
            JournalLineInput(
                account_id=debit_account.id,
                debit_foreign=expense.gross_amount,
                debit_base=expense.gross_base_amount,
                currency_code=expense.currency.code,
                exchange_rate=expense.exchange_rate,
                description=f"Payment — {expense.description}",
                branch=expense.branch,
                party_type="supplier",
                party_id=expense.vendor,
            ),
            JournalLineInput(
                account_id=cash_account.id,
                credit_foreign=expense.gross_amount,
                credit_base=expense.gross_base_amount,
                currency_code=expense.currency.code,
                exchange_rate=expense.exchange_rate,
                description=f"Payment — {expense.description}",
                branch=expense.branch,
            ),
        ],
    )

    expense.payment_status = ExpenseTransaction.PaymentStatus.PAID
    expense.status = ExpenseTransaction.Status.PAID
    expense.save(update_fields=["payment_status", "status", "updated_at"])

    emit_audit_log(
        event_type="expense.paid",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=expense.branch,
        performed_by_id=paid_by_id,
        payload={"payment_date": str(payment_date), "amount_ugx": str(expense.gross_base_amount)},
    )
    return {"journal_id": str(journal.id)}


@transaction.atomic
def reverse_expense(
    *,
    expense_id: UUID,
    reversal_date: date,
    reversed_by_id: UUID | None = None,
    reason: str = "",
    fiscal_period_id: UUID | None = None,
) -> ExpenseTransaction:
    """Reverse a posted expense and release its consumed budget."""
    expense = ExpenseTransaction.objects.select_for_update().get(id=expense_id)
    if expense.status != ExpenseTransaction.Status.POSTED:
        raise ExpenseStatusError("Only POSTED expenses can be reversed.")
    if expense.journal_entry_id is None:
        raise ExpenseStatusError("No journal entry linked — cannot reverse.")

    ensure_date_in_open_period(posting_date=reversal_date, branch=expense.branch)

    reversal = reverse_journal_entry(
        journal_entry_id=expense.journal_entry_id,
        reversal_date=reversal_date,
        created_by_id=reversed_by_id,
        reason=reason or f"Expense reversal: {expense.reference}",
    )

    if fiscal_period_id:
        release_budget(
            fiscal_period_id=fiscal_period_id,
            amount_ugx=expense.base_amount,
            department=expense.department,
            branch=expense.branch,
            project=expense.project,
            expense_category_id=expense.expense_category_id,
        )

    expense.status = ExpenseTransaction.Status.REVERSED
    expense.reversal_journal_entry = reversal
    expense.save(update_fields=["status", "reversal_journal_entry", "updated_at"])

    emit_audit_log(
        event_type="expense.reversed",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=expense.branch,
        performed_by_id=reversed_by_id,
        payload={"reversal_journal_id": str(reversal.id), "reason": reason},
    )
    return expense
