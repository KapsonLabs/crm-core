# Ledgers Skill

Use this guide when you need to post accounting transactions into the `ledgers` engine, generate UGX reports, seed setup data, or add new accounting workflows without breaking ledger integrity.

## Purpose

`ledgers` is the accounting backbone for the ERP ecosystem.

- Operational apps own their own business models.
- Operational services call `ledgers.services.*`.
- `ledgers` does not import operational models.
- All official reporting currency is `UGX`.
- Multi-currency source transactions are supported, but historical conversions are stored at posting time and never recomputed later.

## Golden rules

- Never put accounting logic in models, serializers, or signals.
- Always post through `services/`.
- Always use `transaction.atomic()` around posting workflows.
- Never mutate posted journal FX rates or ledger rows.
- Never update or delete `LedgerEntry`.
- Journals must balance in `UGX` base amounts.
- If you need to correct a posting, reverse it with a compensating journal.

---

## Installation and setup

### 1. Add to `INSTALLED_APPS`

```python
INSTALLED_APPS = [
    ...
    "ledgers",
]
```

### 2. Run migrations

```bash
python manage.py migrate ledgers
```

### 3. Seed the chart of accounts

Call this once per branch (or once globally with `branch=None`). It creates the full default chart of accounts, currencies, and `AccountingConfiguration` for that branch.

```python
from ledgers.seed import seed_default_chart_of_accounts

seed_default_chart_of_accounts(branch=None)                  # UGX only
seed_default_chart_of_accounts(branch=None, currency="USD")  # UGX + USD
seed_default_chart_of_accounts(branch=branch_uuid)           # branch-specific chart
```

What this does:

- Creates `UGX` as the base currency (idempotent).
- Optionally creates a foreign transaction currency.
- Creates or updates the full default chart of accounts.
- Creates or updates `AccountingConfiguration` with the account code map for that branch.

### 4. Create entity subledgers

Whenever an operational entity (customer, supplier, product, warehouse, etc.) is created in an operational app, call:

```python
from ledgers.services.subledger_service import EntitySubledgerRequest, create_default_entity_accounts

subledgers = create_default_entity_accounts(
    request=EntitySubledgerRequest(
        entity_type="customer",        # see full list below
        entity_id="CUST-001",          # unique identifier from operational app
        entity_name="ABC Ltd",
        branch=branch_id,              # UUID or None
        currency_code="UGX",
    )
)
```

Do not use Django signals for this. Call the service explicitly from the operational create flow.

### 5. Open a fiscal period before posting

The engine rejects postings to closed or nonexistent periods. Ensure an open `FiscalPeriod` covers every date you intend to post to.

```python
from ledgers.models import FiscalPeriod
from datetime import date

FiscalPeriod.objects.get_or_create(
    name="May 2026",
    defaults={
        "start_date": date(2026, 5, 1),
        "end_date": date(2026, 5, 31),
        "is_closed": False,
    },
)
```

You can also create periods via the admin or management command. The `utils/periods.py` helper raises `FiscalPeriodClosedError` automatically when a posting date falls outside every open period.

---

## Core architecture

### Models

Main accounting records live in [models.py](models.py).

- `Currency`: master currency list, one base currency only, fixed to `UGX`
- `ExchangeRate`: immutable dated FX rates
- `Account`: chart of accounts
- `ControlAccount`: summarized GL control ledger
- `SubLedgerAccount`: operational entity subsidiary ledger
- `JournalEntry`: draft or posted journal header with transaction currency and base currency
- `JournalLine`: stores both foreign and base amounts
- `LedgerEntry`: append-only posted ledger row — never update or delete
- `SubLedgerEntry`: immutable operational detail that reconciles to control accounts
- `FiscalPeriod`: open/close posting windows
- `AccountingConfiguration`: branch-specific account and engine config
- `RecurringAccrual`: accrual schedules
- `AssetDepreciationSchedule`: depreciation schedules
- `AuditLog`: posting and workflow audit trail — also immutable

### Services

Business logic lives in [services/](services/).

- `journal_service.py`: create, validate, post, reverse journals
- `posting_service.py`: convert posted journals into immutable ledger rows
- `subledger_service.py`: create and map operational entity subledgers to control accounts
- `forex_service.py`: FX retrieval, conversion, realized/unrealized variance
- `inventory_posting_service.py`: inventory purchase, sale, COGS, adjustments, WIP
- `rental_posting_service.py`: rental invoices, payments, deposits, accruals
- `sacco_posting_service.py`: savings, loans, interest, penalties
- `receivable_service.py`: customer invoices, receipts, aging, bad debt
- `payable_service.py`: supplier invoices, payments, aging, accruals
- `accrual_service.py`: recurring accrual schedule generation and runs
- `depreciation_service.py`: asset schedules, depreciation, disposal
- `reconciliation_service.py`: statement matching plus control-account and subledger reconciliation
- `period_service.py`: close and reopen periods
- `audit_service.py`: audit log emission
- `valuation_service.py`: IAS 2 valuation, FIFO/WAC/specific identification, NRV testing
- `costing_service.py`: FIFO/WAC/standard cost and manufacturing costing
- `landed_cost_service.py`: freight, insurance, import duty capitalization and allocation
- `manufacturing_cost_service.py`: WIP, finished goods completion, factory overhead allocation
- `impairment_service.py`: write-downs, write-backs, obsolete inventory provisioning
- `inventory_transfer_service.py`: in-transit and warehouse transfer accounting
- `inventory_reconciliation_service.py`: physical count variance and shrinkage accounting
- `inventory_accrual_service.py`: GRNI accrual and reversal

### Utilities

Shared calculations live in [utils/](utils/).

- `currency.py`: FX lookup, UGX conversion, quantization
- `money.py`: decimal-safe rounding
- `periods.py`: get and validate open periods
- `ledger.py`: balances, trial balance, general ledger
- `reports.py`: balance sheet, income statement, cashflow, profit/loss
- `validators.py`: double-entry and account checks
- `inventory_costing.py`: inventory costing helpers
- `inventory_valuation.py`: valuation and write-down helpers
- `landed_costs.py`: landed cost allocation helpers
- `nrv.py`: NRV and obsolescence helpers
- `inventory_reconciliation.py`: stock variance helpers
- `inventory_reporting.py`: inventory accounting reports

---

## Exception catalog

All exceptions are in [exceptions.py](exceptions.py) and inherit from `AccountingError`.

| Exception | When raised |
|---|---|
| `FiscalPeriodClosedError` | Posting date has no matching open `FiscalPeriod` |
| `JournalBalanceError` | UGX debits ≠ UGX credits in the submitted lines |
| `ImmutableLedgerError` | Attempt to update or delete a `LedgerEntry`, `SubLedgerEntry`, or `AuditLog` |
| `PostingConfigurationError` | `AccountingConfiguration` for the branch is missing a required account key |
| `ReconciliationError` | Bank reconciliation called with `require_full_match=True` but unmatched lines remain |

Catch `AccountingError` as the base class to handle all accounting failures uniformly:

```python
from ledgers.exceptions import AccountingError, FiscalPeriodClosedError

try:
    post_inventory_purchase(...)
except FiscalPeriodClosedError:
    # Period not open — prompt user to open the period or correct the date
    ...
except AccountingError as exc:
    # Any other accounting engine failure
    logger.error("Accounting error: %s", exc)
    raise
```

---

## Restricted control accounts

These account categories have `allows_manual_posting=False`. Posting any `JournalLine` to one of them **without a `subledger_account_id`** is rejected by the engine's control-account guard.

```text
accounts_receivable
accounts_payable
member_savings
loan_receivables
interest_receivable
staff_receivable_control
payroll_payable_control
loan_liability_control
interest_payable_control
loan_penalty_control
consignment_payable_control
```

Inventory, manufacturing, and WIP accounts are **not** restricted — they use the separate `InventoryJournalEntry` system and allow direct GL posting.

When building a custom posting that targets a restricted control account, resolve the subledger first:

```python
from ledgers.models import SubLedgerAccount

subledger = SubLedgerAccount.objects.get(
    parent_control_account__category="accounts_receivable",
    entity_id="CUST-001",
    branch=branch_id,
)
```

Then pass its `id` as `subledger_account_id` on the relevant `JournalLineInput`.

---

## Posting workflow

Every new accounting workflow should follow this shape:

1. Validate source data in the operational service.
2. Resolve configured accounts from `AccountingConfiguration`.
3. Resolve transaction currency and exchange rate.
4. Build `JournalLineInput` rows with foreign and/or base amounts.
5. If the target is a restricted control account, resolve the correct `SubLedgerAccount`.
6. Call `create_and_post_journal()` or a specialized posting service.
7. Let `journal_service` validate balancing in `UGX` and control-account rules.
8. Let `posting_service` create immutable `LedgerEntry` rows and `SubLedgerEntry` rows.
9. Let `audit_service` record the event automatically.

---

## Most important entrypoints

### Seed initial setup

```python
from ledgers.seed import seed_default_chart_of_accounts

seed_default_chart_of_accounts(currency="USD")
```

### Create subledgers for an operational entity

```python
from ledgers.services.subledger_service import EntitySubledgerRequest, create_default_entity_accounts

subledgers = create_default_entity_accounts(
    request=EntitySubledgerRequest(
        entity_type="customer",
        entity_id="0001",
        entity_name="ABC Ltd",
        branch=branch_id,
        currency_code="UGX",
    )
)
```

### Post a simple UGX journal

Use [services/helpers.py](services/helpers.py) for straightforward engine-level postings.

```python
from datetime import date
from decimal import Decimal

from ledgers.services.helpers import create_and_post_journal
from ledgers.services.types import JournalLineInput

journal = create_and_post_journal(
    reference="JE-OPEN-001",
    journal_type="manual_opening",
    posting_date=date(2026, 5, 8),
    description="Opening capital",
    source_module="general",
    source_id="opening-001",
    branch=None,
    created_by_id=user.id,
    idempotency_key="opening-001",
    transaction_currency_code="UGX",
    lines=[
        JournalLineInput(
            account_id=cash_account.id,
            debit_foreign=Decimal("1000000"),
            debit_base=Decimal("1000000"),
            currency_code="UGX",
        ),
        JournalLineInput(
            account_id=equity_account.id,
            credit_foreign=Decimal("1000000"),
            credit_base=Decimal("1000000"),
            currency_code="UGX",
        ),
    ],
)
```

Idempotency keys must be globally unique per posting event. Use the format `"{module}:{source-id}"` to match the conventions used across all specialized posting services (e.g. `"supplier-invoice:INV-001"`, `"supplier-payment:PAY-001"`).

### Use `build_two_line_entry` for simple two-line postings

`build_two_line_entry` is the standard helper for any posting that is a single debit and a single credit. It handles base-amount derivation from the exchange rate and wires up party and subledger references on both sides.

```python
from ledgers.services.helpers import build_two_line_entry, create_and_post_journal

lines = build_two_line_entry(
    debit_account_id=expense_account.id,
    credit_account_id=payable_account.id,
    amount=Decimal("850000"),
    currency="UGX",
    description="Supplier invoice SINV-001",
    branch=branch_id,
    party_type="supplier",
    party_id="SUP-001",
    rate_date=date(2026, 5, 8),                          # used to look up the exchange rate
    debit_subledger_account_id=None,                     # optional — omit for non-restricted accounts
    credit_subledger_account_id=supplier_subledger.id,   # required for accounts_payable
)

create_and_post_journal(
    reference="SINV-001",
    journal_type="supplier_invoice",
    posting_date=date(2026, 5, 8),
    description="Supplier invoice SINV-001",
    source_module="payables",
    source_id="SINV-001",
    branch=branch_id,
    created_by_id=user.id,
    idempotency_key="supplier-invoice:SINV-001",
    lines=lines,
)
```

For multi-line journals (three or more lines), build `JournalLineInput` objects directly.

### Post to a control account with subledger detail

If the target account is a restricted control account such as Accounts Receivable, attach the relevant `subledger_account_id` to the line targeting that account.

```python
create_and_post_journal(
    reference="AR-CTRL-001",
    journal_type="receivable_invoice",
    posting_date=date(2026, 5, 8),
    description="Customer invoice",
    source_module="receivables",
    source_id="invoice-ctrl-001",
    branch=branch_id,
    created_by_id=user.id,
    idempotency_key="invoice-ctrl-001",
    transaction_currency_code="UGX",
    lines=[
        JournalLineInput(
            account_id=receivable_control_gl_account.id,
            debit_foreign=Decimal("250000"),
            debit_base=Decimal("250000"),
            currency_code="UGX",
            subledger_account_id=customer_subledger.id,   # required for restricted control
        ),
        JournalLineInput(
            account_id=revenue_account.id,
            credit_foreign=Decimal("250000"),
            credit_base=Decimal("250000"),
            currency_code="UGX",
        ),
    ],
)
```

### Post a foreign currency journal

If the source transaction is in USD, pass the foreign amount and currency. The engine snapshots the historical exchange rate and derives stored base amounts in `UGX`. You can omit `debit_base`/`credit_base` and let the engine compute them, or supply them explicitly if you have already converted.

```python
journal = create_and_post_journal(
    reference="INV-USD-001",
    journal_type="receivable_invoice",
    posting_date=date(2026, 5, 1),
    description="Customer invoice in USD",
    source_module="receivables",
    source_id="invoice-001",
    branch=None,
    created_by_id=user.id,
    idempotency_key="invoice-001",
    transaction_currency_code="USD",
    lines=[
        JournalLineInput(
            account_id=receivable_account.id,
            debit_foreign=Decimal("100.00"),
            currency_code="USD",
        ),
        JournalLineInput(
            account_id=revenue_account.id,
            credit_foreign=Decimal("100.00"),
            currency_code="USD",
        ),
    ],
)
```

### Use specialized posting services

Prefer specialized services when the transaction belongs to a business domain.

Inventory purchase (IAS 2):

```python
from ledgers.services.inventory_posting_service import post_inventory_purchase

post_inventory_purchase(
    purchase_id="PO-INV-1001",
    posting_date=date(2026, 5, 8),
    amount=Decimal("370000"),
    inventory_item_id=uuid4(),
    warehouse_id=uuid4(),
    quantity_received=Decimal("100"),
    branch=branch_id,
    created_by_id=user.id,
    currency="UGX",
)
```

Landed cost capitalization:

```python
from ledgers.services.landed_cost_service import allocate_landed_costs

allocate_landed_costs(
    shipment_reference="SHIP-1001",
    cost_type="freight",
    allocation_method="quantity",
    amount=Decimal("250000"),
    currency_code="UGX",
    allocation_basis={"item-a": Decimal("10"), "item-b": Decimal("5")},
    allocation_date=date(2026, 5, 5),
    branch=branch_id,
)
```

Inventory impairment / NRV:

```python
from ledgers.services.impairment_service import create_inventory_provision

create_inventory_provision(
    inventory_item_id=uuid4(),
    warehouse_id=uuid4(),
    carrying_value=Decimal("400000"),
    nrv_value=Decimal("325000"),
    assessment_date=date(2026, 5, 31),
    reason="Damaged stock write-down",
    branch=branch_id,
    created_by_id=user.id,
)
```

Manufacturing / WIP:

```python
from ledgers.services.manufacturing_cost_service import post_wip_consumption, complete_finished_goods

post_wip_consumption(
    production_order="MO-1001",
    posting_date=date(2026, 5, 7),
    raw_material_cost=Decimal("750000"),
    branch=branch_id,
    created_by_id=user.id,
)

complete_finished_goods(
    production_order="MO-1001",
    posting_date=date(2026, 5, 9),
    total_cost=Decimal("900000"),
    branch=branch_id,
    created_by_id=user.id,
)
```

GRNI accrual:

```python
from ledgers.services.inventory_accrual_service import accrue_inventory_receipt

accrue_inventory_receipt(
    supplier_invoice_reference="GRN-1001",
    inventory_item_id=uuid4(),
    warehouse_id=uuid4(),
    accrued_amount=Decimal("600000"),
    accrual_date=date(2026, 5, 30),
    branch=branch_id,
    created_by_id=user.id,
)
```

Receivables:

```python
from ledgers.services.receivable_service import create_receivable_invoice

create_receivable_invoice(
    invoice_id=str(invoice.id),
    posting_date=invoice_date,
    amount=Decimal("100.00"),
    revenue_account_id=revenue_account.id,
    customer_id=str(customer.id),
    branch=branch_id,
    created_by_id=user.id,
    currency="USD",
)
```

Payables:

```python
from ledgers.services.payable_service import create_supplier_invoice

create_supplier_invoice(
    invoice_id=str(bill.id),
    posting_date=bill_date,
    amount=Decimal("850.00"),
    expense_account_id=expense_account.id,
    supplier_id=str(supplier.id),
    branch=branch_id,
    created_by_id=user.id,
    currency="USD",
)
```

Rental:

```python
from ledgers.services.rental_posting_service import post_rent_invoice

post_rent_invoice(
    invoice_id=str(lease_invoice.id),
    posting_date=lease_invoice_date,
    amount=Decimal("1200000"),
    branch=branch_id,
    created_by_id=user.id,
    currency="UGX",
)
```

SACCO:

```python
from ledgers.services.sacco_posting_service import post_loan_disbursement

post_loan_disbursement(
    disbursement_id=str(loan.id),
    posting_date=disbursement_date,
    amount=Decimal("5000000"),
    cash_account_id=bank_account.id,
    member_id=str(member.id),
    branch=branch_id,
    created_by_id=user.id,
    currency="UGX",
)
```

---

## Entity types for subledger creation

`create_default_entity_accounts()` accepts the following `entity_type` values. Each creates a distinct set of subledgers linked to their parent control accounts.

| `entity_type` | Subledgers created |
|---|---|
| `customer` | Customer Receivable Ledger (AR control) |
| `supplier` | Supplier Payable Ledger (AP control) |
| `product` | Inventory Asset, Adjustment, COGS, Variance Ledgers |
| `fixed_asset` | Asset Cost, Accumulated Depreciation, Depreciation Expense, Disposal Ledgers |
| `bank_account` | Bank Ledger (cash and cash equivalents control) |
| `wallet` | Wallet Ledger (electronic money control) |
| `warehouse` | Warehouse Inventory Ledger, Warehouse Variance Ledger |
| `sacco_member` | Savings Ledger, Loan Ledger, Interest Ledger |
| `employee` | Employee Advance Ledger, Payroll Liability Ledger |
| `project` | WIP Ledger, Project Cost Ledger, Project Revenue Ledger |
| `work_order` | WIP Ledger, Material Consumption Ledger, Production Variance Ledger |
| `consignment_partner` | Consignment Inventory Ledger, Consignment Settlement Ledger |
| `branch_entity` | Interbranch Receivable, Payable, and Clearing Ledgers |
| `tax_authority` | VAT Input Ledger, VAT Output Ledger, Withholding Tax Ledger |
| `loan_facility` | Loan Principal Ledger, Loan Interest Ledger, Loan Penalty Ledger |

---

## How utility functions should be used

### `utils/currency.py`

Use this for read-only FX operations, not for posting directly.

```python
from ledgers.utils.currency import get_exchange_rate, convert_to_ugx

rate = get_exchange_rate(
    from_currency_code="USD",
    to_currency_code="UGX",
    rate_date=date(2026, 5, 1),
)

ugx_amount = convert_to_ugx(
    amount=Decimal("100.00"),
    from_currency_code="USD",
    rate_date=date(2026, 5, 1),
)
```

Use cases: previewing invoice UGX values before posting, validating external import files, FX-sensitive service calculations.

### `services/forex_service.py`

Use this when you need realized or unrealized FX calculations and adjustment postings.

```python
from ledgers.services.forex_service import calculate_realized_forex_gain_loss

variance = calculate_realized_forex_gain_loss(
    original_foreign_amount=Decimal("100.00"),
    original_exchange_rate=Decimal("3700.000000"),
    settlement_exchange_rate=Decimal("3850.000000"),
)
```

If the result is non-zero, post a forex adjustment:

```python
from ledgers.services.forex_service import post_forex_adjustment

post_forex_adjustment(
    adjustment_id="receivable-payment-001",
    posting_date=date(2026, 5, 15),
    amount_base=variance,
    revaluation_account_id=receivable_account.id,
    branch=branch_id,
    created_by_id=user.id,
    is_realized=True,      # True for settled transactions, False for month-end revaluation
)
```

IAS 21 gain/loss direction enforced by the engine:

- Gain (`amount_base > 0`): DR revaluation account / CR Forex Gain income account
- Loss (`amount_base < 0`): DR Forex Loss expense account / CR revaluation account

### `utils/ledger.py`

Use this for UGX reporting balances only. Always pass `branch` when the deployment is multi-branch to avoid cross-branch aggregation.

```python
from ledgers.utils.ledger import calculate_account_balance, calculate_trial_balance

balance = calculate_account_balance(
    account=receivable_account,
    as_of_date=date(2026, 5, 31),
    branch=branch_id,       # omit for consolidated, pass UUID for branch-specific
)

trial_balance = calculate_trial_balance(
    as_of_date=date(2026, 5, 31),
    branch=branch_id,
)
```

### `utils/reports.py`

**Important**: income statement and profit/loss are period-scoped (only entries within the date range). Balance sheet is cumulative (all entries up to `as_of_date`). These are different query shapes and must not be confused.

```python
from ledgers.utils.reports import (
    generate_balance_sheet,
    generate_income_statement,
    generate_profit_loss,
)

# Cumulative — fetches ALL entries up to as_of_date
balance_sheet = generate_balance_sheet(
    as_of_date=date(2026, 5, 31),
    branch=branch_id,
)

# Period-scoped — fetches ONLY entries between start_date and end_date
income_stmt = generate_income_statement(
    start_date=date(2026, 5, 1),
    end_date=date(2026, 5, 31),
    branch=branch_id,
)

profit_loss = generate_profit_loss(
    start_date=date(2026, 5, 1),
    end_date=date(2026, 5, 31),
    branch=branch_id,
)
```

The income statement and profit/loss reports return `total_income`, `total_expenses`, and `net_profit` keys in the result dict. The balance sheet returns `total_assets` and a `balance_check` (assets − liabilities − equity, which must be zero).

### `services/reconciliation_service.py`

Use this for both bank matching and control-account reconciliation.

```python
from ledgers.services.reconciliation_service import (
    detect_out_of_balance_subledgers,
    reconcile_control_accounts,
    reconcile_bank_statement,
    validate_subledger_integrity,
)

# Control-account reconciliation (GL vs subledger totals)
control_results = reconcile_control_accounts(branch=branch_id)
integrity = validate_subledger_integrity(branch=branch_id)
exceptions = detect_out_of_balance_subledgers(branch=branch_id)

# Bank statement matching — partial matches are allowed by default
result = reconcile_bank_statement(
    bank_account_id=bank_account.id,
    statement_lines=parsed_lines,          # list[BankStatementLine]
    branch=branch_id,
    performed_by_id=user.id,
    require_full_match=False,              # set True to raise ReconciliationError on partial match
)
# result keys: matched, unmatched, matched_count, unmatched_count, is_fully_reconciled
```

Typical pre-close uses: AR/AP control reconciliation, inventory control vs product/warehouse subledgers, subledger integrity pre-validation.

### `utils/inventory_reporting.py`

```python
from ledgers.utils.inventory_reporting import (
    generate_fifo_layer_report,
    generate_inventory_valuation_report,
    generate_nrv_exposure_report,
)

valuation = generate_inventory_valuation_report(
    as_of_date=date(2026, 5, 31),
    branch=branch_id,
)
fifo_layers = generate_fifo_layer_report(branch=branch_id)
nrv_exposure = generate_nrv_exposure_report(branch=branch_id)
```

### `utils/periods.py`

Use this before custom posting flows to guard against posting to closed periods.

```python
from ledgers.utils.periods import ensure_date_in_open_period

period = ensure_date_in_open_period(posting_date=invoice_date, branch=branch_id)
```

### `utils/validators.py`

Use this when constructing custom journal lines or import tools.

```python
from ledgers.utils.validators import validate_double_entry

validate_double_entry(lines)
```

---

## Realized forex example

Scenario:

- Invoice created for `USD 100`
- Invoice date rate: `1 USD = 3,700 UGX`
- Payment date rate: `1 USD = 3,850 UGX`

Result:

- Original carrying amount: `370,000 UGX`
- Settlement amount: `385,000 UGX`
- Realized forex difference: `15,000 UGX` (gain — DR receivable / CR Forex Gain)

Flow:

1. Post the original receivable invoice in USD.
2. Post the payment in USD at the settlement date.
3. Calculate variance using `calculate_realized_forex_gain_loss()`.
4. Post the adjustment using `post_forex_adjustment(..., is_realized=True)`.

---

## Unrealized forex example

Scenario:

- Receivable remains open at month-end
- Carrying rate: `3,700`
- Closing rate: `3,820`

```python
from ledgers.services.forex_service import calculate_unrealized_forex_gain_loss

variance = calculate_unrealized_forex_gain_loss(
    foreign_balance=Decimal("100.00"),
    carrying_exchange_rate=Decimal("3700.000000"),
    closing_exchange_rate=Decimal("3820.000000"),
)
```

Then post an unrealized forex adjustment journal:

```python
post_forex_adjustment(
    adjustment_id=f"unrealized-{subledger_id}-2026-05-31",
    posting_date=date(2026, 5, 31),
    amount_base=variance,
    revaluation_account_id=receivable_account.id,
    branch=branch_id,
    created_by_id=user.id,
    is_realized=False,
)
```

The month-end Celery task handles this automatically for all open foreign-currency subledger accounts. Run it manually if needed:

```python
from ledgers.tasks import run_unrealized_forex_revaluation_task

run_unrealized_forex_revaluation_task(
    revaluation_date_iso="2026-05-31",
    branch_id=str(branch_id),           # optional
    performed_by_id=str(user.id),       # optional
)
```

---

## Reversal example

Never edit posted journals directly.

```python
from ledgers.services.journal_service import reverse_journal_entry

reverse_journal_entry(
    journal_entry_id=journal.id,
    reversal_date=date(2026, 5, 20),
    created_by_id=user.id,
    reason="Operational document cancelled",
)
```

The original journal status becomes `REVERSED`. The reversal journal has the same lines with debits and credits flipped. The net effect on every account balance is zero.

---

## Period close example

```python
from ledgers.services.period_service import close_period

close_period(
    period_id=period.id,
    performed_by_id=user.id,
)
```

Before closing, complete the following steps in order:

1. Run the unrealized forex revaluation task.
2. Run the accrual task.
3. Run the depreciation task.
4. Check `validate_subledger_integrity()` — all control accounts must balance with their subledgers.
5. Check `calculate_trial_balance()` — difference must be `Decimal("0.00")`.
6. Post any required adjusting journals.
7. Close the period.

After the period is closed, any attempt to post to a date within it raises `FiscalPeriodClosedError`.

---

## Task examples

Unrealized forex revaluation (IAS 21.28 — month-end):

```python
from ledgers.tasks import run_unrealized_forex_revaluation_task

run_unrealized_forex_revaluation_task.delay("2026-05-31")
run_unrealized_forex_revaluation_task.delay("2026-05-31", branch_id=str(branch_id))
```

Recurring accruals:

```python
from ledgers.tasks import run_monthly_accruals_task

run_monthly_accruals_task.delay("2026-05-31")
```

Asset depreciation:

```python
from ledgers.tasks import post_monthly_depreciation_task

post_monthly_depreciation_task.delay("2026-05-31")
```

Inventory valuation report:

```python
from ledgers.tasks import run_inventory_valuation_report_task

result = run_inventory_valuation_report_task.delay("2026-05-31")
# result.get() returns {"as_of_date": "2026-05-31", "rows": [...]}
```

NRV impairment test (single item):

```python
from ledgers.tasks import run_inventory_impairment_test_task

result = run_inventory_impairment_test_task.delay(
    inventory_item_id=str(item_id),
    warehouse_id=str(warehouse_id),
    carrying_value="400000",
    nrv_value="325000",
    assessment_date_iso="2026-05-31",
    reason="Damage assessment",
    branch_id=str(branch_id),
)
# result.get() returns None (no write-down needed) or
# {"write_down_id": "...", "write_down_amount": "75000", "journal_id": "..."}
```

All task return values are JSON-serializable (strings, dicts, lists). No `Decimal` or `date` objects are returned raw.

---

## What another agent should do when adding a new posting flow

1. Do not create ledger rows directly.
2. Add a dedicated function under `services/`.
3. Resolve account mappings from `AccountingConfiguration` via `get_configured_account()`.
4. Use `JournalLineInput` (frozen dataclass — all fields are keyword-only).
5. If the flow targets a restricted control account, resolve or create the right `SubLedgerAccount` first.
6. Store `debit_foreign`, `credit_foreign`, `exchange_rate`, and the derived `debit_base`/`credit_base` in UGX.
7. Post via `create_and_post_journal()`.
8. Use `build_two_line_entry()` for single debit / single credit flows.
9. Choose an idempotency key pattern: `"{module}:{source-id}"` (e.g. `"rental:LEASE-001"`).
10. Add tests covering UGX balancing, FX behavior, and subledger reconciliation where relevant.
11. If the flow can settle at a different rate later, include realized FX handling.

---

## What another agent should avoid

- No direct writes to `LedgerEntry`
- No direct writes to `SubLedgerEntry`
- No rate recalculation on posted journals
- No signal-driven postings
- No float math — use `Decimal` everywhere
- No report-time FX recomputation — reports read stored `*_base` amounts only
- No operational-model imports inside `ledgers`
- No `datetime.timedelta(days=30 * n)` for month arithmetic — use the `_add_months()` helper or `calendar.monthrange()`
- No `last_entry.running_balance_base` for balance queries under concurrency — use `Sum()` aggregations

---

## Testing guide

Tests extend `django.test.TestCase` and call posting services directly. The engine requires a seeded chart of accounts and an open fiscal period in the test database.

Minimal setup:

```python
from datetime import date
from django.test import TestCase

from ledgers.seed import seed_default_chart_of_accounts
from ledgers.models import FiscalPeriod


class MyAccountingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_default_chart_of_accounts(currency="USD")
        FiscalPeriod.objects.create(
            name="May 2026",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            is_closed=False,
        )
        # create any additional accounts needed for the test
```

Assertion patterns:

```python
from ledgers.utils.ledger import calculate_trial_balance

# Trial balance must always be zero after any valid posting
self.assertEqual(
    calculate_trial_balance(date(2026, 5, 31))["difference"],
    Decimal("0.00"),
)
```

Use `assertRaises` to verify engine guards:

```python
from ledgers.exceptions import FiscalPeriodClosedError, JournalBalanceError

with self.assertRaises(FiscalPeriodClosedError):
    post_inventory_purchase(..., posting_date=date(2025, 1, 1))  # no open period for this date
```

---

## Files to read first

If you need to make changes, start here:

- [models.py](models.py)
- [services/journal_service.py](services/journal_service.py)
- [services/helpers.py](services/helpers.py)
- [services/subledger_service.py](services/subledger_service.py)
- [services/reconciliation_service.py](services/reconciliation_service.py)
- [services/forex_service.py](services/forex_service.py)
- [utils/currency.py](utils/currency.py)
- [utils/reports.py](utils/reports.py)
- [exceptions.py](exceptions.py)
- [seed.py](seed.py)
- [examples.py](examples.py)
- [tests.py](tests.py)

---

## Standards references

These references were used to shape the accounting and inventory design. Future agents should consult them before changing valuation, FX, impairment, or presentation behavior.

- [IAS 2 Inventories overview](https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/)
- [IAS 21 Foreign Exchange Rates overview](https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/)
- [IAS 16 Property, Plant and Equipment](https://www.ifrs.org/issued-standards/list-of-standards/ias-16-property-plant-and-equipment/)
- [IAS 36 Impairment of Assets](https://www.ifrs.org/issued-standards/list-of-standards/ias-36-impairment-of-assets/)
- [IFRS 15 Revenue from Contracts with Customers](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/)
- [Deloitte IAS 2 summary](https://iasplus.com/api/v1/client/publications/54182/document)

Practical takeaways reflected in this engine:

- Inventory is measured at the lower of cost and NRV.
- FIFO and weighted average are allowed; LIFO is not (IAS 2 prohibits it).
- Specific identification is valid for non-interchangeable items.
- Cost includes purchase, conversion, and other costs to bring inventory to present location and condition.
- Abnormal waste, selling costs, and unrelated admin overhead are excluded from inventory cost.
- Foreign currency transactions use historical exchange rates at recognition and preserve those rates immutably.
- Unrealized FX adjustments are reversed at the start of the next period via the normal accrual reversal mechanism.
- Realized FX differences are recognized in profit or loss for the period in which they arise (IAS 21.28).

---

## Expense Accounting Module (`expense_accounting`)

The `expense_accounting` Django app extends the ERP with a full operational expense engine. It lives alongside `ledgers` and calls into `ledgers.services.*` for all journal/ledger operations. It never writes to `LedgerEntry` directly.

### Package structure

```
expense_accounting/
    models/               ← ExpenseCategory, ExpenseTransaction, ExpenseLine,
                            ExpenseApproval, PrepaidExpenseSchedule,
                            ExpenseBudget, CorporateCardTransaction
    services/             ← all business logic
    repositories/         ← data access
    selectors/            ← read-only query helpers
    reports/              ← UGX report generators
    tasks/                ← Celery scheduled tasks
    utils/                ← calculation helpers (no side effects)
    api/serializers/      ← DRF serializers
    api/views/            ← DRF viewsets
    api/routers/          ← URL router
    tests/                ← full test suite
```

### Expense types and their journal patterns

| `expense_type` | DR | CR |
|---|---|---|
| `operational` / `supplier` | Expense Account | Accounts Payable |
| `supplier` (with VAT) | Expense + VAT Input | Accounts Payable (gross) |
| `employee_reimbursement` | Expense Account | Employee Reimbursement Liability |
| `capital` | Fixed Assets | Accounts Payable |
| `accrual` | Expense Account | Accrued Expense Provision |
| `corporate_card` | Expense Account | Corporate Card Clearing |
| `prepaid` / `deferred` | Prepaid Expenses (asset) | AP / Cash (initial posting) |

Prepaid amortization (monthly):

```
DR Expense Account
CR Prepaid Expenses (asset)
```

Employee reimbursement settlement:

```
DR Employee Reimbursement Liability
CR Cash / Bank
```

Expense payment (AP settlement):

```
DR Accounts Payable
CR Cash / Bank
```

### Lifecycle states

```text
DRAFT → SUBMITTED → APPROVED → POSTED → PAID
                 → REJECTED
                 ← REVERSED  (from POSTED)
```

### Create and post a supplier expense

```python
from decimal import Decimal
from datetime import date

from expense_accounting.services.expense_posting_service import (
    create_expense, submit_expense, post_expense, pay_expense,
)
from expense_accounting.services.expense_approval_service import approve_expense

# 1. Create draft
expense = create_expense(
    reference="EXP-001",
    expense_category_id=category.id,
    vendor="ACME Supplies Ltd",
    amount=Decimal("500000"),
    tax_amount=Decimal("90000"),          # VAT 18%
    description="Office supplies May 2026",
    expense_date=date(2026, 5, 10),
    created_by_id=user.id,
    currency_code="UGX",
    department="Operations",
    project="",
    branch=branch_id,
)

# 2. Submit for approval
submit_expense(expense_id=expense.id, submitted_by_id=user.id)

# 3. Manager approves (level 1 for ≤500,000 UGX)
approve_expense(expense_id=expense.id, approver_id=manager.id, remarks="Approved")

# 4. Post to ledger — DR Expense + DR VAT Input / CR AP
post_expense(
    expense_id=expense.id,
    posted_by_id=user.id,
    fiscal_period_id=period.id,     # optional, required only if enforce_budget=True
    enforce_budget=True,
)

# 5. Record payment when AP is settled
pay_expense(
    expense_id=expense.id,
    payment_date=date(2026, 5, 20),
    cash_account_id=bank_account.id,
    paid_by_id=user.id,
)
```

### Create a prepaid expense and amortize it

```python
from expense_accounting.services.prepaid_expense_service import (
    create_prepaid_schedule, amortize_prepaid_expense,
)

# After expense is submitted and auto-approved (requires_approval=False):
schedule = create_prepaid_schedule(
    expense=expense,
    start_date=date(2026, 5, 1),
    end_date=date(2027, 4, 30),          # 12 months
    prepaid_account=prepaid_account,     # Account(category="prepaid_expenses")
    credit_account=ap_account,           # Account(category="accounts_payable")
)

# Each month — run via Celery or manually:
result = amortize_prepaid_expense(
    schedule=schedule,
    amortization_date=date(2026, 5, 31),
    expense_account=operating_expense_account,
    prepaid_account=prepaid_account,
)
# result: {"journal_id": "...", "period": 1, "amount_ugx": Decimal("100000.00")}
```

### Employee reimbursement

```python
from expense_accounting.services.reimbursement_service import (
    submit_employee_claim, approve_claim, reimburse_employee,
)

submit_employee_claim(expense=expense, submitted_by_id=employee_id)
approve_claim(expense_id=expense.id, approver_id=manager_id)
# post_expense(...) posts DR Expense / CR Employee Reimbursement Liability
post_expense(expense_id=expense.id, posted_by_id=user.id, enforce_budget=False)

reimburse_employee(
    expense=expense,
    payment_date=date(2026, 5, 25),
    cash_account=bank_account,
    reimbursement_liability_account=reimb_liability_account,
    paid_by_id=user.id,
)
```

### Budget control

```python
from expense_accounting.services.expense_budget_service import (
    check_budget_availability, consume_budget, release_budget, generate_budget_variance,
)
from expense_accounting.models import ExpenseBudget

# Create a budget for a department/period
ExpenseBudget.objects.create(
    fiscal_period_id=period.id,
    department="Marketing",
    branch=branch_id,
    expense_category=category,
    budget_amount=Decimal("2000000"),
    created_by=user.id,
)

# Check availability before posting (raises BudgetExceededError if exceeded)
check_budget_availability(
    fiscal_period_id=period.id,
    amount_ugx=Decimal("500000"),
    department="Marketing",
    branch=branch_id,
    expense_category_id=category.id,
    raise_on_exceeded=True,
)

# post_expense() handles consume_budget() automatically when fiscal_period_id is passed.

# Variance report
variances = generate_budget_variance(fiscal_period_id=period.id, branch=branch_id)
# [{"department": ..., "budget_amount": ..., "consumed_amount": ..., "variance": ..., "is_over_budget": bool}]
```

### Tax / VAT handling

```python
from expense_accounting.services.expense_tax_service import (
    calculate_input_vat, calculate_withholding_tax, split_tax_amounts,
)

# Tax-exclusive (net amount given, compute VAT on top)
net, vat = split_tax_amounts(amount=Decimal("200000"), tax_rate=Decimal("0.18"), tax_inclusive=False)
# net=200000, vat=36000

# Tax-inclusive (gross given, split into net + tax)
net, vat = split_tax_amounts(amount=Decimal("236000"), tax_rate=Decimal("0.18"), tax_inclusive=True)
# net≈200000, vat≈36000

# Withholding tax
wht = calculate_withholding_tax(gross_amount=Decimal("500000"), wht_rate=Decimal("0.06"))
# wht=30000
```

### Approval thresholds

| Amount (UGX base) | Level | Label |
|---|---|---|
| ≤ 500,000 | 1 | manager |
| 500,001 – 5,000,000 | 2 | finance |
| > 5,000,000 | 3 | cfo |

```python
from expense_accounting.services.expense_approval_service import determine_approval_level

level, label = determine_approval_level(base_amount_ugx=Decimal("2000000"))
# (2, "finance")
```

If `ExpenseCategory.requires_approval=False` or `amount ≤ approval_required_above`, the expense skips approval and moves directly to `APPROVED` on submit.

### Expense allocation

```python
from expense_accounting.services.expense_allocation_service import (
    split_expense_by_percentage, allocate_to_departments,
)

# Split across departments
allocations = allocate_to_departments(
    expense=expense,
    dept_percentages={
        "Operations": Decimal("60"),
        "Administration": Decimal("40"),
    },
)
```

### Celery tasks

```python
from expense_accounting.tasks.expense_tasks import (
    run_prepaid_amortization_task,
    run_accrual_reversals_task,
    escalate_pending_approvals_task,
    run_budget_monitoring_task,
    send_reimbursement_reminders_task,
)

run_prepaid_amortization_task.delay("2026-05-31")
run_accrual_reversals_task.delay("2026-06-01")
escalate_pending_approvals_task.delay()
run_budget_monitoring_task.delay(str(period.id))
send_reimbursement_reminders_task.delay()
```

### Reports

```python
from expense_accounting.reports.expense_reports import (
    generate_expense_analysis,
    generate_department_expense_report,
    generate_project_expense_report,
    generate_budget_variance_report,
    generate_prepaid_expense_report,
    generate_expense_aging_report,
    generate_employee_claims_report,
    generate_expense_trend_report,
    generate_corporate_card_report,
    generate_tax_deduction_report,
)

analysis = generate_expense_analysis(
    start_date=date(2026, 5, 1),
    end_date=date(2026, 5, 31),
    branch=branch_id,
)
# {"total_net_ugx": ..., "total_tax_ugx": ..., "total_gross_ugx": ..., "by_category": [...]}
```

All reports output UGX values from stored `base_amount` and `tax_base_amount` fields. They never recompute FX conversions at report time.

### Exception catalog (expense_accounting)

| Exception | When raised |
|---|---|
| `ExpenseStatusError` | Action attempted in wrong lifecycle state (e.g. posting a DRAFT) |
| `ExpenseApprovalError` | No pending approval found, or approval constraint violated |
| `BudgetExceededError` | Posting would exceed a budget allocation |
| `BudgetNotFoundError` | No budget configured for dimension combination |
| `PrepaidScheduleError` | Prepaid schedule state invalid (already exists, not active, zero balance) |
| `ExpenseConfigurationError` | Missing required field (project/department) or account mapping |
| `AllocationError` | Allocation percentages do not sum to 100 |

### API endpoints

All routes are registered under `expense_accounting/api/routers/expense_routers.py`:

| Prefix | ViewSet | Key custom actions |
|---|---|---|
| `/expense-categories/` | `ExpenseCategoryViewSet` | — |
| `/expenses/` | `ExpenseTransactionViewSet` | `submit`, `approve`, `reject`, `post`, `pay`, `reverse` |
| `/prepaid-schedules/` | `PrepaidExpenseScheduleViewSet` | — |
| `/expense-budgets/` | `ExpenseBudgetViewSet` | — |
| `/corporate-cards/` | `CorporateCardTransactionViewSet` | — |
| `/expense-reports/` | `ExpenseReportsViewSet` | `analysis`, `department`, `project`, `budget-variance`, `prepaid`, `aging`, `employee-claims`, `trend`, `tax` |

Permission model: `IsAccountingViewer` for reads, `IsAccountingManager` for writes and postings.

### New accounts added to `ledgers` chart of accounts

| Code | Name | Type | Category |
|---|---|---|---|
| 1300 | Prepaid Expenses | asset | `prepaid_expenses` |
| 5500 | Operating Expenses | expense | `operating_expenses` |
| 5501 | Department Expense Control | expense | `department_expense_control` |
| 2500 | Employee Reimbursement Liability | liability | `employee_reimbursement_liability` |
| 2510 | Corporate Card Clearing | liability | `corporate_card_clearing` |
| 2520 | Accrued Expense Provision | liability | `accrued_expense_provision` |

These are seeded by `ledgers.seed.seed_default_chart_of_accounts()` — no additional seeding step is needed.

### What to avoid in expense_accounting

- Never write to `LedgerEntry`, `SubLedgerEntry`, or `AuditLog` directly.
- Never put posting logic in serializers or models.
- Never use Django signals for expense posting.
- Never use float arithmetic — always `Decimal`.
- Always call `ensure_date_in_open_period()` before posting a journal.
- Always wrap posting workflows in `@transaction.atomic`.
- Correct errors via `reverse_expense()`, not by editing posted records.
