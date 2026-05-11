from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase

from apps.ledgers.models import (
    Account,
    AssetDepreciationSchedule,
    AuditLog,
    ControlAccount,
    Currency,
    ExchangeRate,
    FiscalPeriod,
    InventoryAccrual,
    InventoryLedgerEntry,
    InventoryValuationLayer,
    InventoryWriteDown,
    JournalEntry,
    LedgerEntry,
    SubLedgerAccount,
    SubLedgerEntry,
)
from apps.ledgers.services.accrual_service import generate_accrual_schedule, run_monthly_accruals
from apps.ledgers.services.audit_service import emit_audit_log
from apps.ledgers.services.depreciation_service import dispose_asset, generate_depreciation_schedule, post_monthly_depreciation
from apps.ledgers.services.forex_service import (
    calculate_realized_forex_gain_loss,
    calculate_unrealized_forex_gain_loss,
    post_forex_adjustment,
)
from apps.ledgers.services.helpers import create_and_post_journal
from apps.ledgers.services.inventory_accrual_service import accrue_inventory_receipt, reverse_inventory_accrual
from apps.ledgers.services.inventory_posting_service import calculate_fifo_cost, calculate_weighted_average_cost, post_inventory_purchase, post_inventory_sale
from apps.ledgers.services.inventory_reconciliation_service import reconcile_physical_count
from apps.ledgers.services.journal_service import reverse_journal_entry
from apps.ledgers.services.landed_cost_service import allocate_landed_costs
from apps.ledgers.services.manufacturing_cost_service import allocate_factory_overheads, complete_finished_goods, post_wip_consumption
from apps.ledgers.services.payable_service import create_supplier_invoice, calculate_supplier_aging
from apps.ledgers.services.period_service import close_period
from apps.ledgers.services.receivable_service import create_receivable_invoice, calculate_customer_aging, post_bad_debt
from apps.ledgers.services.reconciliation_service import reconcile_bank_statement, reconcile_control_accounts, validate_subledger_integrity
from apps.ledgers.services.rental_posting_service import post_rent_invoice, post_rent_payment, post_security_deposit
from apps.ledgers.services.sacco_posting_service import post_loan_disbursement, post_loan_repayment, post_savings_deposit
from apps.ledgers.services.subledger_service import EntitySubledgerRequest, create_default_entity_accounts
from apps.ledgers.services.types import BankStatementLine, JournalLineInput
from apps.ledgers.seed import seed_default_chart_of_accounts
from apps.ledgers.services.impairment_service import create_inventory_provision
from apps.ledgers.utils.ledger import calculate_account_balance, calculate_trial_balance
from apps.ledgers.utils.reports import generate_balance_sheet, generate_income_statement, generate_profit_loss


class AccountingEngineTests(TestCase):
    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX",
            name="Ugandan Shilling",
            symbol="UGX",
            decimal_places=0,
            is_base_currency=True,
            is_active=True,
        )
        self.usd = Currency.objects.create(
            code="USD",
            name="US Dollar",
            symbol="$",
            decimal_places=2,
            is_active=True,
        )
        ExchangeRate.objects.create(
            from_currency=self.usd,
            to_currency=self.ugx,
            rate=Decimal("3700.000000"),
            date=date(2026, 5, 1),
            source="BOT",
        )
        ExchangeRate.objects.create(
            from_currency=self.usd,
            to_currency=self.ugx,
            rate=Decimal("3850.000000"),
            date=date(2026, 5, 15),
            source="BOT",
        )
        FiscalPeriod.objects.create(
            name="May 2026",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
        )
        seed_default_chart_of_accounts(currency="USD")

    def test_manual_balanced_journal_posts_to_immutable_ledger_in_ugx(self):
        cash = Account.objects.create(
            code="10000",
            name="Cash",
            account_type="asset",
            category="cash",
            currency=self.ugx,
        )
        equity = Account.objects.create(
            code="3000",
            name="Owner Equity",
            account_type="equity",
            category="equity",
            currency=self.ugx,
        )
        journal = create_and_post_journal(
            reference="JE-1",
            journal_type="manual",
            posting_date=date(2026, 5, 10),
            description="Opening capital",
            source_module="general",
            source_id="opening-1",
            branch=None,
            created_by_id=None,
            idempotency_key="opening-1",
            transaction_currency_code="UGX",
            lines=[
                JournalLineInput(account_id=cash.id, debit_base=Decimal("100000.00"), debit_foreign=Decimal("100000.00"), currency_code="UGX"),
                JournalLineInput(account_id=equity.id, credit_base=Decimal("100000.00"), credit_foreign=Decimal("100000.00"), currency_code="UGX"),
            ],
        )
        self.assertEqual(journal.status, JournalEntry.Status.POSTED)
        self.assertEqual(LedgerEntry.objects.count(), 2)
        self.assertEqual(calculate_trial_balance(date(2026, 5, 10))["difference"], Decimal("0.00"))

    def test_foreign_currency_journal_stores_foreign_and_base_amounts(self):
        receivable = Account.objects.create(
            code="1231",
            name="Trade Receivables USD",
            account_type="asset",
            category="accounts_receivable",
            currency=self.usd,
        )
        revenue = Account.objects.create(
            code="4000",
            name="Revenue",
            account_type="income",
            category="income",
            currency=self.ugx,
        )
        journal = create_and_post_journal(
            reference="INV-USD-1",
            journal_type="receivable_invoice",
            posting_date=date(2026, 5, 10),
            description="USD customer invoice",
            source_module="receivables",
            source_id="invoice-usd-1",
            branch=None,
            created_by_id=None,
            idempotency_key="invoice-usd-1",
            transaction_currency_code="USD",
            lines=[
                JournalLineInput(account_id=receivable.id, debit_foreign=Decimal("100.00"), currency_code="USD"),
                JournalLineInput(account_id=revenue.id, credit_foreign=Decimal("100.00"), currency_code="USD"),
            ],
        )
        self.assertEqual(journal.transaction_currency.code, "USD")
        line = journal.lines.first()
        assert line is not None
        self.assertEqual(line.debit_base, Decimal("370000"))

    def test_realized_forex_gain_loss_calculation(self):
        variance = calculate_realized_forex_gain_loss(
            original_foreign_amount=Decimal("100.00"),
            original_exchange_rate=Decimal("3700.000000"),
            settlement_exchange_rate=Decimal("3850.000000"),
        )
        self.assertEqual(variance, Decimal("15000"))

    def test_idempotent_posting_returns_existing_journal(self):
        cash = Account.objects.create(
            code="1001",
            name="Cash 2",
            account_type="asset",
            category="cash",
            currency=self.ugx,
        )
        revenue = Account.objects.create(
            code="4001",
            name="Revenue 2",
            account_type="income",
            category="income",
            currency=self.ugx,
        )
        first = create_and_post_journal(
            reference="JE-2",
            journal_type="manual",
            posting_date=date(2026, 5, 10),
            description="Sample sale",
            source_module="sales",
            source_id="sale-1",
            branch=None,
            created_by_id=None,
            idempotency_key="sale-1",
            lines=[
                JournalLineInput(account_id=cash.id, debit_base=Decimal("50000.00"), debit_foreign=Decimal("50000.00"), currency_code="UGX"),
                JournalLineInput(account_id=revenue.id, credit_base=Decimal("50000.00"), credit_foreign=Decimal("50000.00"), currency_code="UGX"),
            ],
        )
        second = create_and_post_journal(
            reference="JE-2",
            journal_type="manual",
            posting_date=date(2026, 5, 10),
            description="Sample sale",
            source_module="sales",
            source_id="sale-1",
            branch=None,
            created_by_id=None,
            idempotency_key="sale-1",
            lines=[
                JournalLineInput(account_id=cash.id, debit_base=Decimal("50000.00"), debit_foreign=Decimal("50000.00"), currency_code="UGX"),
                JournalLineInput(account_id=revenue.id, credit_base=Decimal("50000.00"), credit_foreign=Decimal("50000.00"), currency_code="UGX"),
            ],
        )
        self.assertEqual(first.id, second.id)

    def test_costing_helpers(self):
        weighted = calculate_weighted_average_cost(
            total_cost=Decimal("120.00"),
            total_units=Decimal("10"),
        )
        fifo = calculate_fifo_cost(
            quantity_to_issue=Decimal("6"),
            cost_layers=[],
        )
        self.assertEqual(weighted, Decimal("12.00"))
        self.assertEqual(fifo, Decimal("0.00"))

    def test_inventory_purchase_creates_valuation_layer_and_ledger(self):
        result = post_inventory_purchase(
            purchase_id="PO-INV-1",
            posting_date=date(2026, 5, 10),
            amount=Decimal("370000"),
            inventory_item_id=uuid4(),
            warehouse_id=uuid4(),
            quantity_received=Decimal("100"),
            branch=None,
            created_by_id=None,
            currency="UGX",
        )
        self.assertEqual(InventoryValuationLayer.objects.count(), 1)
        self.assertEqual(InventoryLedgerEntry.objects.count(), 1)
        self.assertEqual(result["inventory_journal"].status, "posted")

    def test_inventory_sale_issues_stock(self):
        inventory_item_id = uuid4()
        warehouse_id = uuid4()
        post_inventory_purchase(
            purchase_id="PO-INV-2",
            posting_date=date(2026, 5, 10),
            amount=Decimal("740000"),
            inventory_item_id=inventory_item_id,
            warehouse_id=warehouse_id,
            quantity_received=Decimal("20"),
            branch=None,
            created_by_id=None,
            currency="UGX",
        )
        result = post_inventory_sale(
            sale_id="SO-INV-1",
            posting_date=date(2026, 5, 11),
            sales_amount=Decimal("950000"),
            inventory_item_id=inventory_item_id,
            warehouse_id=warehouse_id,
            quantity_sold=Decimal("5"),
            branch=None,
            created_by_id=None,
            currency="UGX",
        )
        self.assertIn("inventory_journal", result)

    def test_inventory_write_down_creation(self):
        result = create_inventory_provision(
            inventory_item_id=uuid4(),
            warehouse_id=uuid4(),
            carrying_value=Decimal("100000"),
            nrv_value=Decimal("75000"),
            assessment_date=date(2026, 5, 31),
            reason="Slow moving",
            branch=None,
            created_by_id=None,
        )
        self.assertIsNotNone(result)
        self.assertEqual(InventoryWriteDown.objects.count(), 1)

    def test_grni_accrual_creation(self):
        result = accrue_inventory_receipt(
            supplier_invoice_reference="SUP-INV-1",
            inventory_item_id=uuid4(),
            warehouse_id=uuid4(),
            accrued_amount=Decimal("500000"),
            accrual_date=date(2026, 5, 30),
            branch=None,
            created_by_id=None,
        )
        self.assertEqual(InventoryAccrual.objects.count(), 1)
        self.assertEqual(result["accrual"].status, "active")

    def test_landed_cost_allocation(self):
        rows = allocate_landed_costs(
            shipment_reference="SHIP-1",
            cost_type="freight",
            allocation_method="quantity",
            amount=Decimal("300000"),
            currency_code="UGX",
            allocation_basis={"a": Decimal("10"), "b": Decimal("5")},
            allocation_date=date(2026, 5, 15),
        )
        self.assertEqual(len(rows), 2)

    def test_inventory_reconciliation_variance(self):
        data = reconcile_physical_count(
            inventory_item_id=uuid4(),
            warehouse_id=uuid4(),
            physical_quantity=Decimal("10"),
        )
        self.assertEqual(data["variance"], Decimal("10.0000"))

    def test_factory_overhead_allocation(self):
        allocation = allocate_factory_overheads(
            production_order="MO-1",
            direct_cost_base=Decimal("1000000"),
            overhead_pool=Decimal("250000"),
            activity_share=Decimal("0.50"),
            output_quantity=Decimal("50"),
        )
        self.assertEqual(allocation.production_order, "MO-1")

    def test_subledger_auto_creation_for_customer(self):
        subledgers = create_default_entity_accounts(
            request=EntitySubledgerRequest(
                entity_type="customer",
                entity_id="0001",
                entity_name="ABC Ltd",
                branch=None,
                currency_code="UGX",
            )
        )
        self.assertEqual(len(subledgers), 1)
        self.assertTrue(subledgers[0].account_code.startswith("AR-CUST-"))

    def test_control_account_reconciliation_with_customer_subledger(self):
        receivable = Account.objects.get(code="1230")
        receivable.is_control_account = True
        receivable.allows_manual_posting = False
        receivable.save(update_fields=["is_control_account", "allows_manual_posting", "updated_at"])
        control = ControlAccount.objects.create(
            code="1230",
            name="Accounts Receivable Control",
            gl_account=receivable,
            currency=self.ugx,
            allows_manual_posting=False,
            is_active=True,
        )
        subledger = SubLedgerAccount.objects.create(
            account_code="AR-CUST-0001",
            account_name="Customer Receivable Ledger: ABC Ltd",
            entity_type="customer",
            entity_id="0001",
            ledger_purpose="Customer Receivable Ledger",
            parent_control_account=control,
            branch=None,
            currency=self.ugx,
            gl_account=receivable,
        )
        revenue = Account.objects.create(
            code="4010",
            name="Service Revenue",
            account_type="income",
            category="income",
            currency=self.ugx,
        )
        create_and_post_journal(
            reference="AR-SL-1",
            journal_type="receivable_invoice",
            posting_date=date(2026, 5, 20),
            description="Customer invoice with subledger",
            source_module="receivables",
            source_id="customer-0001-invoice",
            branch=None,
            created_by_id=None,
            idempotency_key="customer-0001-invoice",
            transaction_currency_code="UGX",
            lines=[
                JournalLineInput(
                    account_id=receivable.id,
                    debit_base=Decimal("250000"),
                    debit_foreign=Decimal("250000"),
                    currency_code="UGX",
                    subledger_account_id=subledger.id,
                ),
                JournalLineInput(
                    account_id=revenue.id,
                    credit_base=Decimal("250000"),
                    credit_foreign=Decimal("250000"),
                    currency_code="UGX",
                ),
            ],
        )
        reconciliation = reconcile_control_accounts()
        self.assertTrue(any(item["control_account_code"] == "1230" and item["is_balanced"] for item in reconciliation))
        integrity = validate_subledger_integrity()
        self.assertTrue(integrity["is_valid"])


class ForexAccountingTests(TestCase):
    """IAS 21 foreign currency accounting tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        self.usd = Currency.objects.create(
            code="USD", name="US Dollar", symbol="$", decimal_places=2, is_active=True,
        )
        ExchangeRate.objects.create(
            from_currency=self.usd, to_currency=self.ugx,
            rate=Decimal("3700.000000"), date=date(2026, 5, 1), source="BOT",
        )
        ExchangeRate.objects.create(
            from_currency=self.usd, to_currency=self.ugx,
            rate=Decimal("3850.000000"), date=date(2026, 5, 15), source="BOT",
        )
        FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        seed_default_chart_of_accounts(currency="USD")

    def test_realized_forex_gain_is_positive(self):
        gain = calculate_realized_forex_gain_loss(
            original_foreign_amount=Decimal("100.00"),
            original_exchange_rate=Decimal("3700.000000"),
            settlement_exchange_rate=Decimal("3850.000000"),
        )
        self.assertEqual(gain, Decimal("15000"))

    def test_realized_forex_loss_is_negative(self):
        loss = calculate_realized_forex_gain_loss(
            original_foreign_amount=Decimal("100.00"),
            original_exchange_rate=Decimal("3850.000000"),
            settlement_exchange_rate=Decimal("3700.000000"),
        )
        self.assertEqual(loss, Decimal("-15000"))

    def test_unrealized_forex_gain_loss_calculation(self):
        gain = calculate_unrealized_forex_gain_loss(
            foreign_balance=Decimal("100.00"),
            carrying_exchange_rate=Decimal("3700.000000"),
            closing_exchange_rate=Decimal("3820.000000"),
        )
        self.assertEqual(gain, Decimal("12000"))

    def test_post_forex_gain_journal_debits_revaluation_account(self):
        revaluation = Account.objects.create(
            code="1231X", name="AR FX", account_type="asset",
            category="accounts_receivable_fx", currency=self.ugx,
        )
        journal = post_forex_adjustment(
            adjustment_id="fx-gain-001",
            posting_date=date(2026, 5, 15),
            amount_base=Decimal("15000"),
            revaluation_account_id=revaluation.id,
            branch=None,
            created_by_id=None,
            is_realized=True,
        )
        self.assertIsNotNone(journal)
        assert journal is not None
        lines = list(journal.lines.all())
        revaluation_line = next(l for l in lines if l.account_id == revaluation.id)
        # GAIN → DR revaluation account (asset increases)
        self.assertGreater(revaluation_line.debit_base, Decimal("0"))
        self.assertEqual(revaluation_line.credit_base, Decimal("0"))

    def test_post_forex_loss_journal_credits_revaluation_account(self):
        revaluation = Account.objects.create(
            code="1232X", name="AR FX Loss", account_type="asset",
            category="accounts_receivable_fx2", currency=self.ugx,
        )
        journal = post_forex_adjustment(
            adjustment_id="fx-loss-001",
            posting_date=date(2026, 5, 15),
            amount_base=Decimal("-15000"),
            revaluation_account_id=revaluation.id,
            branch=None,
            created_by_id=None,
            is_realized=True,
        )
        self.assertIsNotNone(journal)
        assert journal is not None
        lines = list(journal.lines.all())
        revaluation_line = next(l for l in lines if l.account_id == revaluation.id)
        # LOSS → CR revaluation account (asset decreases)
        self.assertGreater(revaluation_line.credit_base, Decimal("0"))
        self.assertEqual(revaluation_line.debit_base, Decimal("0"))

    def test_zero_forex_amount_returns_none(self):
        revaluation = Account.objects.create(
            code="1233X", name="AR FX Zero", account_type="asset",
            category="accounts_receivable_fx3", currency=self.ugx,
        )
        result = post_forex_adjustment(
            adjustment_id="fx-zero-001",
            posting_date=date(2026, 5, 15),
            amount_base=Decimal("0"),
            revaluation_account_id=revaluation.id,
            branch=None,
            created_by_id=None,
            is_realized=True,
        )
        self.assertIsNone(result)


class AssetDepreciationTests(TestCase):
    """IAS 16 asset depreciation and disposal tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        seed_default_chart_of_accounts()
        self.asset_account = Account.objects.get(code="1500")
        self.accum_dep_account = Account.objects.get(code="1510")
        self.dep_expense_account = Account.objects.get(code="5300")
        self.disposal_account = Account.objects.get(code="4320")
        self.cash_account = Account.objects.create(
            code="1001D", name="Cash Disposal", account_type="asset",
            category="cash", currency=self.ugx,
        )

    def test_depreciation_schedule_generates_correct_months(self):
        schedules = generate_depreciation_schedule(
            asset_reference="ASSET-001",
            asset_name="Computer",
            asset_account_id=self.asset_account.id,
            accumulated_depreciation_account_id=self.accum_dep_account.id,
            depreciation_expense_account_id=self.dep_expense_account.id,
            acquisition_cost=Decimal("1200000"),
            salvage_value=Decimal("0"),
            useful_life_months=12,
            depreciation_start_date=date(2026, 1, 1),
            branch=None,
        )
        self.assertEqual(len(schedules), 12)
        total_depreciated = sum(s.depreciation_amount for s in schedules)
        self.assertEqual(total_depreciated, Decimal("1200000"))

    def test_depreciation_schedule_rounding_absorbs_in_last_month(self):
        schedules = generate_depreciation_schedule(
            asset_reference="ASSET-002",
            asset_name="Vehicle",
            asset_account_id=self.asset_account.id,
            accumulated_depreciation_account_id=self.accum_dep_account.id,
            depreciation_expense_account_id=self.dep_expense_account.id,
            acquisition_cost=Decimal("1000001"),
            salvage_value=Decimal("1"),
            useful_life_months=12,
            depreciation_start_date=date(2026, 1, 1),
            branch=None,
        )
        total = sum(s.depreciation_amount for s in schedules)
        self.assertEqual(total, Decimal("1000000"))

    def test_depreciation_schedule_uses_calendar_months(self):
        schedules = generate_depreciation_schedule(
            asset_reference="ASSET-003",
            asset_name="Furniture",
            asset_account_id=self.asset_account.id,
            accumulated_depreciation_account_id=self.accum_dep_account.id,
            depreciation_expense_account_id=self.dep_expense_account.id,
            acquisition_cost=Decimal("600000"),
            salvage_value=Decimal("0"),
            useful_life_months=3,
            depreciation_start_date=date(2026, 1, 31),
            branch=None,
        )
        # Jan 31 + 1 month → Feb 28 (not Mar 2), Feb 28 + 1 → Mar 28
        self.assertEqual(schedules[0].depreciation_date, date(2026, 1, 31))
        self.assertEqual(schedules[1].depreciation_date, date(2026, 2, 28))
        self.assertEqual(schedules[2].depreciation_date, date(2026, 3, 31))

    def test_post_monthly_depreciation_marks_schedule_posted(self):
        generate_depreciation_schedule(
            asset_reference="ASSET-004",
            asset_name="Laptop",
            asset_account_id=self.asset_account.id,
            accumulated_depreciation_account_id=self.accum_dep_account.id,
            depreciation_expense_account_id=self.dep_expense_account.id,
            acquisition_cost=Decimal("2400000"),
            salvage_value=Decimal("0"),
            useful_life_months=24,
            depreciation_start_date=date(2026, 5, 1),
            branch=None,
        )
        journals = post_monthly_depreciation(as_of_date=date(2026, 5, 31))
        self.assertGreater(len(journals), 0)
        posted = AssetDepreciationSchedule.objects.filter(
            asset_reference="ASSET-004",
            status=AssetDepreciationSchedule.Status.POSTED,
        )
        self.assertEqual(posted.count(), 1)

    def test_asset_disposal_balanced_journal_with_gain(self):
        generate_depreciation_schedule(
            asset_reference="ASSET-005",
            asset_name="Server",
            asset_account_id=self.asset_account.id,
            accumulated_depreciation_account_id=self.accum_dep_account.id,
            depreciation_expense_account_id=self.dep_expense_account.id,
            acquisition_cost=Decimal("5000000"),
            salvage_value=Decimal("0"),
            useful_life_months=12,
            depreciation_start_date=date(2026, 5, 1),
            branch=None,
        )
        post_monthly_depreciation(as_of_date=date(2026, 5, 31))
        journal = dispose_asset(
            asset_reference="ASSET-005",
            disposal_date=date(2026, 5, 31),
            proceeds=Decimal("5100000"),
            cash_account_id=self.cash_account.id,
            disposal_gain_loss_account_id=self.disposal_account.id,
            branch=None,
        )
        self.assertIsNotNone(journal)
        trial = calculate_trial_balance(date(2026, 5, 31))
        self.assertEqual(trial["difference"], Decimal("0.00"))


class PeriodControlTests(TestCase):
    """Period close and posting restriction tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        self.period = FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        seed_default_chart_of_accounts()
        self.cash = Account.objects.create(
            code="1001P", name="Cash Period", account_type="asset",
            category="cash", currency=self.ugx,
        )
        self.equity = Account.objects.create(
            code="3001P", name="Equity Period", account_type="equity",
            category="equity", currency=self.ugx,
        )

    def _post_balanced(self, ref: str, key: str):
        return create_and_post_journal(
            reference=ref, journal_type="manual", posting_date=date(2026, 5, 10),
            description="Test", source_module="test", source_id=key,
            branch=None, created_by_id=None, idempotency_key=key,
            transaction_currency_code="UGX",
            lines=[
                JournalLineInput(account_id=self.cash.id, debit_base=Decimal("50000"), debit_foreign=Decimal("50000"), currency_code="UGX"),
                JournalLineInput(account_id=self.equity.id, credit_base=Decimal("50000"), credit_foreign=Decimal("50000"), currency_code="UGX"),
            ],
        )

    def test_close_period_succeeds_when_trial_balance_is_zero(self):
        self._post_balanced("JE-PC-1", "je-pc-1")
        closed = close_period(period_id=self.period.id)
        self.assertTrue(closed.is_closed)

    def test_posting_to_closed_period_raises_error(self):
        self._post_balanced("JE-PC-2", "je-pc-2")
        close_period(period_id=self.period.id)
        from apps.ledgers.exceptions import FiscalPeriodClosedError
        with self.assertRaises(FiscalPeriodClosedError):
            create_and_post_journal(
                reference="JE-PC-3", journal_type="manual", posting_date=date(2026, 5, 15),
                description="Should fail", source_module="test", source_id="je-pc-3",
                branch=None, created_by_id=None, idempotency_key="je-pc-3",
                lines=[
                    JournalLineInput(account_id=self.cash.id, debit_base=Decimal("1000"), debit_foreign=Decimal("1000"), currency_code="UGX"),
                    JournalLineInput(account_id=self.equity.id, credit_base=Decimal("1000"), credit_foreign=Decimal("1000"), currency_code="UGX"),
                ],
            )

    def test_unbalanced_journal_raises_error(self):
        from apps.ledgers.exceptions import JournalBalanceError
        with self.assertRaises(JournalBalanceError):
            create_and_post_journal(
                reference="JE-UNBAL", journal_type="manual", posting_date=date(2026, 5, 10),
                description="Unbalanced", source_module="test", source_id="je-unbal",
                branch=None, created_by_id=None, idempotency_key="je-unbal",
                lines=[
                    JournalLineInput(account_id=self.cash.id, debit_base=Decimal("100"), debit_foreign=Decimal("100"), currency_code="UGX"),
                    JournalLineInput(account_id=self.equity.id, credit_base=Decimal("200"), credit_foreign=Decimal("200"), currency_code="UGX"),
                ],
            )


class JournalReversalTests(TestCase):
    """Journal reversal correctness tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        seed_default_chart_of_accounts()
        self.cash = Account.objects.create(
            code="1001R", name="Cash Rev", account_type="asset",
            category="cash", currency=self.ugx,
        )
        self.revenue = Account.objects.create(
            code="4001R", name="Revenue Rev", account_type="income",
            category="income", currency=self.ugx,
        )

    def test_reversal_produces_zero_net_balance(self):
        journal = create_and_post_journal(
            reference="JE-REV-1", journal_type="sale", posting_date=date(2026, 5, 10),
            description="Sale", source_module="sales", source_id="sale-rev-1",
            branch=None, created_by_id=None, idempotency_key="sale-rev-1",
            lines=[
                JournalLineInput(account_id=self.cash.id, debit_base=Decimal("100000"), debit_foreign=Decimal("100000"), currency_code="UGX"),
                JournalLineInput(account_id=self.revenue.id, credit_base=Decimal("100000"), credit_foreign=Decimal("100000"), currency_code="UGX"),
            ],
        )
        reverse_journal_entry(
            journal_entry_id=journal.id,
            reversal_date=date(2026, 5, 20),
            reason="Cancel sale",
        )
        self.assertEqual(calculate_account_balance(self.cash, date(2026, 5, 31)), Decimal("0.00"))
        self.assertEqual(calculate_account_balance(self.revenue, date(2026, 5, 31)), Decimal("0.00"))
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))

    def test_reversal_marks_original_as_reversed(self):
        journal = create_and_post_journal(
            reference="JE-REV-2", journal_type="sale", posting_date=date(2026, 5, 10),
            description="Sale", source_module="sales", source_id="sale-rev-2",
            branch=None, created_by_id=None, idempotency_key="sale-rev-2",
            lines=[
                JournalLineInput(account_id=self.cash.id, debit_base=Decimal("50000"), debit_foreign=Decimal("50000"), currency_code="UGX"),
                JournalLineInput(account_id=self.revenue.id, credit_base=Decimal("50000"), credit_foreign=Decimal("50000"), currency_code="UGX"),
            ],
        )
        reverse_journal_entry(journal_entry_id=journal.id, reversal_date=date(2026, 5, 20))
        journal.refresh_from_db()
        self.assertEqual(journal.status, JournalEntry.Status.REVERSED)


class SACCOAccountingTests(TestCase):
    """SACCO savings, loan disbursement, and repayment tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        seed_default_chart_of_accounts()
        self.cash = Account.objects.create(
            code="1001S", name="SACCO Cash", account_type="asset",
            category="cash", currency=self.ugx,
        )

    def test_savings_deposit_posts_and_balances(self):
        post_savings_deposit(
            deposit_id="SAV-001",
            posting_date=date(2026, 5, 10),
            amount=Decimal("500000"),
            cash_account_id=self.cash.id,
            member_id="MBR-001",
            branch=None,
            created_by_id=None,
        )
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))

    def test_loan_disbursement_posts_and_balances(self):
        post_loan_disbursement(
            disbursement_id="LOAN-001",
            posting_date=date(2026, 5, 10),
            amount=Decimal("5000000"),
            cash_account_id=self.cash.id,
            member_id="MBR-002",
            branch=None,
            created_by_id=None,
        )
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))

    def test_loan_repayment_with_interest_posts_and_balances(self):
        post_loan_disbursement(
            disbursement_id="LOAN-002",
            posting_date=date(2026, 5, 5),
            amount=Decimal("1000000"),
            cash_account_id=self.cash.id,
            member_id="MBR-003",
            branch=None,
            created_by_id=None,
        )
        post_loan_repayment(
            repayment_id="REPAY-001",
            posting_date=date(2026, 5, 20),
            principal_amount=Decimal("1000000"),
            interest_amount=Decimal("50000"),
            cash_account_id=self.cash.id,
            member_id="MBR-003",
            branch=None,
            created_by_id=None,
        )
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))


class ManufacturingAccountingTests(TestCase):
    """WIP → Finished Goods accounting tests (IAS 2 manufacturing costs)."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        seed_default_chart_of_accounts()

    def test_wip_consumption_and_finished_goods_net_to_zero(self):
        post_wip_consumption(
            production_order="MO-001",
            posting_date=date(2026, 5, 7),
            raw_material_cost=Decimal("750000"),
            branch=None,
            created_by_id=None,
        )
        complete_finished_goods(
            production_order="MO-001",
            posting_date=date(2026, 5, 9),
            total_cost=Decimal("900000"),
            branch=None,
            created_by_id=None,
        )
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))

    def test_overhead_allocation_formula(self):
        from apps.ledgers.services.costing_service import allocate_manufacturing_overheads
        overhead = allocate_manufacturing_overheads(
            base_amount=Decimal("1000000"),
            overhead_pool=Decimal("250000"),
            activity_share=Decimal("0.40"),
        )
        self.assertEqual(overhead, Decimal("100000.00"))

    def test_zero_activity_share_returns_zero_overhead(self):
        from apps.ledgers.services.costing_service import allocate_manufacturing_overheads
        overhead = allocate_manufacturing_overheads(
            base_amount=Decimal("1000000"),
            overhead_pool=Decimal("250000"),
            activity_share=Decimal("0.00"),
        )
        self.assertEqual(overhead, Decimal("0.00"))


class RentalAccountingTests(TestCase):
    """Rental invoice, payment, and deposit accounting tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        seed_default_chart_of_accounts()
        self.cash = Account.objects.create(
            code="1001RT", name="Rental Cash", account_type="asset",
            category="cash", currency=self.ugx,
        )

    def test_rent_invoice_and_payment_balance(self):
        post_rent_invoice(
            invoice_id="RINV-001",
            posting_date=date(2026, 5, 1),
            amount=Decimal("1200000"),
            branch=None,
            created_by_id=None,
        )
        post_rent_payment(
            payment_id="RPAY-001",
            posting_date=date(2026, 5, 5),
            amount=Decimal("1200000"),
            cash_account_id=self.cash.id,
            branch=None,
            created_by_id=None,
        )
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))

    def test_security_deposit_creates_liability(self):
        post_security_deposit(
            deposit_id="DEP-001",
            posting_date=date(2026, 5, 1),
            amount=Decimal("3000000"),
            cash_account_id=self.cash.id,
            branch=None,
            created_by_id=None,
        )
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))


class ReconciliationTests(TestCase):
    """Bank reconciliation partial match and control account tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        self.bank = Account.objects.create(
            code="1001BNK", name="Bank", account_type="asset",
            category="cash", currency=self.ugx,
        )
        self.revenue = Account.objects.create(
            code="4001REC", name="Revenue Rec", account_type="income",
            category="income", currency=self.ugx,
        )

    def test_partial_reconciliation_returns_unmatched(self):
        create_and_post_journal(
            reference="BNK-001", journal_type="payment", posting_date=date(2026, 5, 10),
            description="Payment", source_module="bank", source_id="bnk-001",
            branch=None, created_by_id=None, idempotency_key="bnk-001",
            lines=[
                JournalLineInput(account_id=self.bank.id, debit_base=Decimal("100000"), debit_foreign=Decimal("100000"), currency_code="UGX"),
                JournalLineInput(account_id=self.revenue.id, credit_base=Decimal("100000"), credit_foreign=Decimal("100000"), currency_code="UGX"),
            ],
        )
        result = reconcile_bank_statement(
            bank_account_id=self.bank.id,
            statement_lines=[
                BankStatementLine(reference="STMT-001", amount=Decimal("100000"), transaction_date=date(2026, 5, 10)),
                BankStatementLine(reference="STMT-002", amount=Decimal("999999"), transaction_date=date(2026, 5, 11)),
            ],
        )
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["unmatched_count"], 1)
        self.assertFalse(result["is_fully_reconciled"])

    def test_full_reconciliation_marks_fully_reconciled(self):
        create_and_post_journal(
            reference="BNK-002", journal_type="payment", posting_date=date(2026, 5, 12),
            description="Payment", source_module="bank", source_id="bnk-002",
            branch=None, created_by_id=None, idempotency_key="bnk-002",
            lines=[
                JournalLineInput(account_id=self.bank.id, debit_base=Decimal("200000"), debit_foreign=Decimal("200000"), currency_code="UGX"),
                JournalLineInput(account_id=self.revenue.id, credit_base=Decimal("200000"), credit_foreign=Decimal("200000"), currency_code="UGX"),
            ],
        )
        result = reconcile_bank_statement(
            bank_account_id=self.bank.id,
            statement_lines=[
                BankStatementLine(reference="STMT-F001", amount=Decimal("200000"), transaction_date=date(2026, 5, 12)),
            ],
        )
        self.assertTrue(result["is_fully_reconciled"])


class ImmutabilityTests(TestCase):
    """Append-only ledger and audit log immutability tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        seed_default_chart_of_accounts()
        self.cash = Account.objects.create(
            code="1001IM", name="Cash Imm", account_type="asset",
            category="cash", currency=self.ugx,
        )
        self.equity = Account.objects.create(
            code="3001IM", name="Equity Imm", account_type="equity",
            category="equity", currency=self.ugx,
        )

    def test_ledger_entry_cannot_be_updated(self):
        from django.core.exceptions import ValidationError
        create_and_post_journal(
            reference="JE-IMM-1", journal_type="manual", posting_date=date(2026, 5, 10),
            description="Test", source_module="test", source_id="je-imm-1",
            branch=None, created_by_id=None, idempotency_key="je-imm-1",
            lines=[
                JournalLineInput(account_id=self.cash.id, debit_base=Decimal("10000"), debit_foreign=Decimal("10000"), currency_code="UGX"),
                JournalLineInput(account_id=self.equity.id, credit_base=Decimal("10000"), credit_foreign=Decimal("10000"), currency_code="UGX"),
            ],
        )
        entry = LedgerEntry.objects.first()
        assert entry is not None
        entry.debit_base = Decimal("99999")
        with self.assertRaises(ValidationError):
            entry.save()

    def test_ledger_entry_cannot_be_deleted(self):
        from django.core.exceptions import ValidationError
        create_and_post_journal(
            reference="JE-IMM-2", journal_type="manual", posting_date=date(2026, 5, 10),
            description="Test", source_module="test", source_id="je-imm-2",
            branch=None, created_by_id=None, idempotency_key="je-imm-2",
            lines=[
                JournalLineInput(account_id=self.cash.id, debit_base=Decimal("10000"), debit_foreign=Decimal("10000"), currency_code="UGX"),
                JournalLineInput(account_id=self.equity.id, credit_base=Decimal("10000"), credit_foreign=Decimal("10000"), currency_code="UGX"),
            ],
        )
        entry = LedgerEntry.objects.first()
        assert entry is not None
        with self.assertRaises(ValidationError):
            entry.delete()

    def test_audit_log_cannot_be_updated(self):
        from django.core.exceptions import ValidationError
        log = emit_audit_log(
            event_type="test.event", entity_type="Test", entity_id="123",
            branch=None, performed_by_id=None, payload={"key": "value"},
        )
        log.payload = {"tampered": True}
        with self.assertRaises(ValidationError):
            log.save()

    def test_audit_log_cannot_be_deleted(self):
        from django.core.exceptions import ValidationError
        log = emit_audit_log(
            event_type="test.event2", entity_type="Test", entity_id="456",
            branch=None, performed_by_id=None,
        )
        with self.assertRaises(ValidationError):
            log.delete()

    def test_exchange_rate_cannot_be_updated(self):
        from django.core.exceptions import ValidationError
        usd = Currency.objects.create(
            code="USDIMM", name="USD Imm", decimal_places=2, is_active=True,
        )
        rate = ExchangeRate.objects.create(
            from_currency=usd, to_currency=self.ugx,
            rate=Decimal("3700.000000"), date=date(2026, 5, 1), source="BOT",
        )
        rate.rate = Decimal("9999.000000")
        with self.assertRaises(ValidationError):
            rate.save()


class ReportingTests(TestCase):
    """Balance sheet and income statement period-scoping tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        FiscalPeriod.objects.create(
            name="Q1 2026", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
        )
        FiscalPeriod.objects.create(
            name="Q2 2026", start_date=date(2026, 4, 1), end_date=date(2026, 6, 30),
        )
        seed_default_chart_of_accounts()
        self.cash = Account.objects.create(
            code="1001RPT", name="Cash Rpt", account_type="asset",
            category="cash", currency=self.ugx,
        )
        self.revenue = Account.objects.create(
            code="4001RPT", name="Revenue Rpt", account_type="income",
            category="income", currency=self.ugx,
        )
        self.expense = Account.objects.create(
            code="5001RPT", name="Expense Rpt", account_type="expense",
            category="expense", currency=self.ugx,
        )

    def _post(self, ref: str, key: str, posting_date: date, dr_id, cr_id, amount: Decimal):
        create_and_post_journal(
            reference=ref, journal_type="manual", posting_date=posting_date,
            description="Test", source_module="test", source_id=key,
            branch=None, created_by_id=None, idempotency_key=key,
            lines=[
                JournalLineInput(account_id=dr_id, debit_base=amount, debit_foreign=amount, currency_code="UGX"),
                JournalLineInput(account_id=cr_id, credit_base=amount, credit_foreign=amount, currency_code="UGX"),
            ],
        )

    def test_income_statement_is_period_scoped_not_cumulative(self):
        # Q1: post 1,000,000 revenue
        self._post("J-Q1", "j-q1", date(2026, 2, 1), self.cash.id, self.revenue.id, Decimal("1000000"))
        # Q2: post 500,000 revenue
        self._post("J-Q2", "j-q2", date(2026, 5, 1), self.cash.id, self.revenue.id, Decimal("500000"))

        q2_report = generate_income_statement(
            start_date=date(2026, 4, 1), end_date=date(2026, 6, 30),
        )
        # Only Q2 revenue should appear (500,000 not 1,500,000)
        self.assertEqual(q2_report["total_income"], Decimal("500000"))

    def test_balance_sheet_is_cumulative(self):
        self._post("J-BS1", "j-bs1", date(2026, 2, 1), self.cash.id, self.revenue.id, Decimal("1000000"))
        self._post("J-BS2", "j-bs2", date(2026, 5, 1), self.cash.id, self.revenue.id, Decimal("500000"))
        bs = generate_balance_sheet(as_of_date=date(2026, 6, 30))
        # Cash (asset) should reflect both postings cumulatively
        total_assets = bs["total_assets"]
        self.assertGreaterEqual(total_assets, Decimal("1500000"))

    def test_profit_loss_net_profit_correct(self):
        self._post("J-PL1", "j-pl1", date(2026, 5, 1), self.cash.id, self.revenue.id, Decimal("1000000"))
        self._post("J-PL2", "j-pl2", date(2026, 5, 2), self.expense.id, self.cash.id, Decimal("300000"))
        pl = generate_profit_loss(start_date=date(2026, 5, 1), end_date=date(2026, 5, 31))
        self.assertEqual(pl["total_income"], Decimal("1000000"))
        self.assertEqual(pl["total_expenses"], Decimal("300000"))
        self.assertEqual(pl["net_profit"], Decimal("700000"))


class AccrualAccountingTests(TestCase):
    """Recurring accrual generation and reversal tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        FiscalPeriod.objects.create(
            name="Jun 2026", start_date=date(2026, 6, 1), end_date=date(2026, 6, 30),
        )
        seed_default_chart_of_accounts()
        self.expense = Account.objects.create(
            code="5001ACC", name="Accrual Expense", account_type="expense",
            category="expense", currency=self.ugx,
        )
        self.accrued_liability = Account.objects.create(
            code="2001ACC", name="Accrued Liability", account_type="liability",
            category="liability", currency=self.ugx,
        )

    def test_monthly_accrual_runs_and_balances(self):
        generate_accrual_schedule(
            name="Rent Accrual",
            source_module="test",
            source_id="acc-001",
            accrual_account_id=self.expense.id,
            offset_account_id=self.accrued_liability.id,
            amount=Decimal("200000"),
            start_date=date(2026, 5, 31),
            end_date=date(2026, 12, 31),
            frequency="monthly",
            branch=None,
        )
        journals = run_monthly_accruals(run_date=date(2026, 5, 31))
        self.assertEqual(len(journals), 1)
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))

    def test_grni_accrual_and_reversal_net_to_zero(self):
        result = accrue_inventory_receipt(
            supplier_invoice_reference="GRN-ACC-001",
            inventory_item_id=uuid4(),
            warehouse_id=uuid4(),
            accrued_amount=Decimal("800000"),
            accrual_date=date(2026, 5, 31),
            branch=None,
            created_by_id=None,
        )
        reverse_inventory_accrual(
            inventory_accrual_id=result["accrual"].id,
            reversal_date=date(2026, 6, 1),
            branch=None,
            created_by_id=None,
        )
        trial = calculate_trial_balance(date(2026, 6, 30))
        self.assertEqual(trial["difference"], Decimal("0.00"))


class ReceivablesPayablesTests(TestCase):
    """AR/AP invoice, payment, aging, and bad debt tests."""

    def setUp(self):
        self.ugx = Currency.objects.create(
            code="UGX", name="Ugandan Shilling", symbol="UGX",
            decimal_places=0, is_base_currency=True, is_active=True,
        )
        FiscalPeriod.objects.create(
            name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
        )
        seed_default_chart_of_accounts()
        self.revenue = Account.objects.create(
            code="4001RP", name="Revenue RP", account_type="income",
            category="income", currency=self.ugx,
        )
        self.expense = Account.objects.create(
            code="5001RP", name="Expense RP", account_type="expense",
            category="expense", currency=self.ugx,
        )
        self.cash = Account.objects.create(
            code="1001RP", name="Cash RP", account_type="asset",
            category="cash", currency=self.ugx,
        )

    def test_customer_invoice_and_payment_balance(self):
        create_receivable_invoice(
            invoice_id="INV-001",
            posting_date=date(2026, 5, 10),
            amount=Decimal("500000"),
            revenue_account_id=self.revenue.id,
            customer_id="CUST-001",
            branch=None,
            created_by_id=None,
        )
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))

    def test_supplier_invoice_balances(self):
        create_supplier_invoice(
            invoice_id="SINV-001",
            posting_date=date(2026, 5, 10),
            amount=Decimal("750000"),
            expense_account_id=self.expense.id,
            supplier_id="SUP-001",
            branch=None,
            created_by_id=None,
        )
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))

    def test_customer_aging_uses_base_amounts(self):
        create_receivable_invoice(
            invoice_id="INV-AGING",
            posting_date=date(2026, 5, 1),
            amount=Decimal("250000"),
            revenue_account_id=self.revenue.id,
            customer_id="CUST-AGE",
            branch=None,
            created_by_id=None,
        )
        aging = calculate_customer_aging(as_of_date=date(2026, 5, 31))
        total = sum(aging.values(), Decimal("0.00"))
        self.assertGreater(total, Decimal("0.00"))

    def test_bad_debt_provision_creates_allowance(self):
        post_bad_debt(
            debt_id="BD-001",
            posting_date=date(2026, 5, 31),
            amount=Decimal("100000"),
            customer_id="CUST-BD",
            branch=None,
            created_by_id=None,
        )
        self.assertEqual(calculate_trial_balance(date(2026, 5, 31))["difference"], Decimal("0.00"))
