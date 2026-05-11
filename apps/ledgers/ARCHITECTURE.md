# Ledgers Accounting Engine

This app is the accounting backbone for ERP modules. Operational apps own business objects and invoke `ledgers.services.*`; the accounting app never imports operational models.

## Audit strategy

- Every journal lifecycle event emits an `AuditLog`.
- Journal entries remain editable only while in `draft`; ledger rows are append-only and immutable.
- Reversals create compensating journals instead of changing history.
- Control-account activity is audit-safe because summarized GL postings can carry immutable `SubLedgerEntry` detail for each operational entity.

## Permissions strategy

- `IsAccountingViewer` grants read access to authenticated users.
- `IsAccountingManager` gates posting, reversals, master data maintenance, and period control.
- Production teams can extend this with branch-aware permission filters in viewsets and repositories.
- Manual posting to control accounts should be restricted by configuration and only allowed where the engine explicitly permits it.

## Reporting architecture

- Reports are assembled from immutable `LedgerEntry` rows.
- `repositories/reporting_repository.py` supplies query shapes.
- `utils/reports.py` provides balance sheet, income statement, cashflow, and profit/loss builders.
- All official reports read stored `*_base` amounts only and therefore always render in `UGX`.
- Inventory accounting reports are assembled from immutable `InventoryLedgerEntry` rows and `InventoryValuationLayer` layers.
- Inventory valuation follows IAS 2 lower-of-cost-and-NRV, with FIFO, weighted average, and specific identification support.
- Landed costs, GRNI, WIP, write-downs, write-backs, and warehouse-level valuation are handled through dedicated inventory services rather than operational models.
- Subsidiary-ledger reporting is assembled from immutable `SubLedgerEntry` rows linked back to `JournalLine` or `InventoryJournalLine`.

## Control Accounts

- `Account` remains the chart-of-accounts backbone for the general ledger.
- `ControlAccount` formalizes GL summary accounts such as Accounts Receivable, Accounts Payable, Inventory Control, Fixed Asset Control, and similar ERP-style summarized ledgers.
- `SubLedgerAccount` represents operational entity ledgers such as a customer receivable ledger, supplier payable ledger, product valuation ledger, bank ledger, project WIP ledger, or member loan ledger.
- Each `SubLedgerAccount` maps to exactly one `ControlAccount`.
- The general ledger stays summarized while subsidiary detail is stored separately and reconciled automatically.

## Auto-Creation Strategy

- Operational entity creation should call `services/subledger_service.py`.
- The service resolves the correct control-account mapping, generates a structured ledger code, and creates the required subledger set for the entity type.
- Example entity mappings include customers to AR control, suppliers to AP control, products to inventory control, warehouses to warehouse inventory/variance ledgers, and assets to fixed asset related ledgers.
- The engine does not use Django signals for auto-creation; operational services must call the service explicitly.

## Reconciliation Strategy

- `services/reconciliation_service.py` compares each control-account GL balance with the sum of its `SubLedgerEntry` balances.
- This supports ERP-style reconciliations such as AR Control vs customer ledgers, AP Control vs supplier ledgers, and Inventory Control vs product or warehouse ledgers.
- Any mismatch is surfaced through `reconcile_control_accounts()`, `validate_subledger_integrity()`, and `detect_out_of_balance_subledgers()`.

## Period close workflow

1. Stop operational posting for the target branch/period.
2. Run accrual and depreciation tasks.
3. Review reconciliation and trial balance exceptions.
4. Review control-account vs subledger reconciliation exceptions.
5. Post adjusting journals.
6. Mark `FiscalPeriod.is_closed=True` and record approver metadata.

## Integration pattern

Operational services call accounting services after their own transaction input is finalized:

```python
from ledgers.services.inventory_posting_service import post_inventory_purchase

post_inventory_purchase(
    purchase_id=str(purchase.id),
    posting_date=purchase.received_at.date(),
    amount=purchase.total_cost,
    branch=purchase.branch_id,
    created_by_id=user.id,
)
```

## Exchange rate management strategy

- `Currency` defines the single system base currency, fixed to `UGX`.
- `ExchangeRate` rows are append-only and immutable; corrections are handled by inserting a new dated rate.
- Posting workflows snapshot both the transaction currency and the exact exchange rate used on each journal and ledger row.
- Realized and unrealized forex adjustments are posted through `services/forex_service.py` rather than by mutating historical journals.
