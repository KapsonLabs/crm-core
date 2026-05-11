# Django ERP Accounting Engine — Skill.md

## Overview

This skill defines the complete architecture, accounting principles, implementation patterns, services, posting workflows, subledger architecture, inventory accounting engine, and multi-currency infrastructure required to build a production-grade Django ERP Accounting Engine from scratch.

The engine is intended to support:

* Inventory Management
* Manufacturing
* Warehousing
* Rental Management
* SACCO / Financial Institution Management
* Accounts Receivable
* Accounts Payable
* Asset Management
* Accrual Accounting
* Multi-Branch Accounting
* Multi-Currency Accounting
* Financial Reporting
* Subledger Accounting
* IFRS-Compliant Inventory Valuation

---

# Core Design Philosophy

The accounting engine must:

* Follow double-entry accounting principles
* Use immutable ledger architecture
* Use service-layer architecture
* Keep models thin
* Prevent direct mutation of historical accounting records
* Maintain full auditability
* Support operational ERP modules without tightly coupling to them

The accounting engine acts as the financial backbone for the ERP ecosystem.

Operational modules must NEVER contain accounting logic.

---

# Architectural Principles

## 1. Service Layer Architecture

ALL accounting logic must exist in:

```bash
services/
```

Example:

```bash
accounting/
    services/
        journal_service.py
        posting_service.py
        inventory_posting_service.py
        valuation_service.py
        costing_service.py
        receivable_service.py
        payable_service.py
        accrual_service.py
        depreciation_service.py
        reconciliation_service.py
        forex_service.py
        subledger_service.py
```

NEVER:

* Put accounting logic in models
* Put accounting logic in serializers
* Use signals for financial posting

---

## 2. Immutable Ledger Design

Ledger entries must:

* Be append-only
* Never be updated after posting
* Never be deleted
* Preserve full accounting history

Corrections must happen via:

* Reversal journals
* Adjustment journals

---

## 3. Transaction Safety

ALL posting workflows must use:

```python
transaction.atomic()
```

This guarantees financial integrity.

---

# IFRS / IAS Standards To Implement

The engine must align with:

## Core Standards

* IAS 1 — Presentation of Financial Statements
* IAS 2 — Inventories
* IAS 21 — Effects of Changes in Foreign Exchange Rates
* IAS 16 — Property, Plant and Equipment
* IAS 23 — Borrowing Costs
* IAS 36 — Impairment of Assets
* IFRS 13 — Fair Value Measurement
* IFRS 15 — Revenue from Contracts with Customers

References:

* [https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/](https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/](https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ias-16-property-plant-and-equipment/](https://www.ifrs.org/issued-standards/list-of-standards/ias-16-property-plant-and-equipment/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ias-36-impairment-of-assets/](https://www.ifrs.org/issued-standards/list-of-standards/ias-36-impairment-of-assets/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ifrs-13-fair-value-measurement/](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-13-fair-value-measurement/)

---

# Base Currency Rules

## Default Currency

The base/reporting currency is:

```text
UGX (Ugandan Shilling)
```

The system must:

* Support multiple currencies
* Preserve historical exchange rates
* Store foreign transaction values
* Store UGX-equivalent values
* Generate all official reports in UGX

References:

* [https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/](https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/)

---

# Core Accounting Models

## Account

Represents the Chart of Accounts.

Fields:

```python
code
name
account_type
category
parent
currency
branch
is_control_account
allows_manual_posting
is_active
```

Support:

* Hierarchical COA
* Control accounts
* Subledgers
* Branch accounting

---

## JournalEntry

Fields:

```python
reference
journal_type
transaction_currency
exchange_rate
base_currency
source_module
source_id
status
posted_at
reversed_entry
branch
created_by
```

Statuses:

```text
draft
posted
reversed
cancelled
```

---

## JournalLine

Fields:

```python
journal_entry
account
debit_foreign
credit_foreign
debit_base
credit_base
currency
exchange_rate
party_type
party_id
branch
```

Rules:

* Debits MUST equal credits
* Base currency MUST be UGX

---

## LedgerEntry

Immutable financial movement.

Fields:

```python
account
journal_line
currency
exchange_rate
debit_foreign
credit_foreign
debit_base
credit_base
running_balance_base
branch
```

Rules:

* Append-only
* Immutable
* Full audit trail

---

## Currency

Fields:

```python
code
name
symbol
decimal_places
is_base_currency
is_active
```

---

## ExchangeRate

Fields:

```python
from_currency
to_currency
rate
date
source
created_at
```

Rules:

* Historical rates immutable
* Used rates preserved permanently

---

## FiscalPeriod

Fields:

```python
name
start_date
end_date
is_closed
closed_at
```

---

## RecurringAccrual

Fields:

```python
name
start_date
end_date
frequency
amount
expense_account
accrual_account
```

---

## AssetDepreciationSchedule

Fields:

```python
asset_reference
purchase_amount
salvage_value
useful_life_months
depreciation_method
monthly_amount
```

Methods:

* Straight line
* Declining balance

---

# Subledger + Control Account Architecture

The ERP must implement:

* General Ledger
* Control Accounts
* Subsidiary Ledgers (Subledgers)

References:

* [https://learn.microsoft.com/en-us/dynamics365/finance/general-ledger/ledger-subledger](https://learn.microsoft.com/en-us/dynamics365/finance/general-ledger/ledger-subledger)

Core principle:

The General Ledger contains summarized balances.

Operational entities maintain detailed subledger balances.

Examples:

```text
Accounts Receivable Control
    -> Customer Subledgers

Accounts Payable Control
    -> Supplier Subledgers

Inventory Control
    -> Product Subledgers
```

---

# Automatic Ledger Creation

The following entities MUST auto-create subledgers when created.

## Products / Inventory Items

Auto-create:

* Inventory Asset Ledger
* Inventory Adjustment Ledger
* COGS Ledger
* Inventory Variance Ledger

Parent:

```text
Inventory Control Account
```

---

## Customers

Auto-create:

* Customer Receivable Ledger

Parent:

```text
Accounts Receivable Control Account
```

---

## Suppliers

Auto-create:

* Supplier Payable Ledger

Parent:

```text
Accounts Payable Control Account
```

---

## Fixed Assets

Auto-create:

* Asset Cost Ledger
* Accumulated Depreciation Ledger
* Depreciation Expense Ledger
* Disposal Ledger

---

## Warehouses

Auto-create:

* Warehouse Inventory Ledger
* Warehouse Variance Ledger

---

## Bank Accounts

Auto-create:

* Bank Ledger

---

## Mobile Money Wallets

Examples:

* MTN MoMo
* Airtel Money
* PayPal
* Stripe Clearing

---

## SACCO Members

Auto-create:

* Savings Ledger
* Loan Ledger
* Interest Ledger

---

## Employees

Auto-create:

* Salary Advance Ledger
* Payroll Liability Ledger

---

## Projects / Cost Centers

Auto-create:

* WIP Ledger
* Project Cost Ledger
* Project Revenue Ledger

---

## Manufacturing Work Orders

Auto-create:

* WIP Ledger
* Production Variance Ledger
* Material Consumption Ledger

---

## Branches

Auto-create:

* Interbranch Receivable Ledger
* Interbranch Payable Ledger
* Branch Clearing Ledger

---

# Inventory Accounting Engine

The inventory accounting engine must support:

* FIFO
* Weighted Average Cost
* Specific Identification
* Standard Costing
* Inventory Valuation
* Landed Costs
* Inventory Write-downs
* NRV Testing
* Manufacturing Costing
* WIP Accounting
* Inventory Transfers
* Batch Costing
* Serial Costing
* Multi-Warehouse Valuation
* Inventory Aging
* Stock Reconciliation
* Shrinkage Accounting
* Inventory Accruals

IMPORTANT:

LIFO MUST NOT be supported.

IAS 2 prohibits LIFO.

Reference:

* [https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/](https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/)

---

# Inventory Accounting Models

## InventoryValuationLayer

Tracks FIFO/WAC layers.

Fields:

```python
inventory_item_id
warehouse_id
batch_id
quantity_remaining
unit_cost
base_unit_cost
currency
exchange_rate
acquisition_date
source_transaction
```

---

## InventoryLedgerEntry

Fields:

```python
inventory_item
warehouse
quantity_in
quantity_out
running_quantity
inventory_value
inventory_value_base
valuation_layer
journal_line
```

---

## InventoryWriteDown

Fields:

```python
inventory_item
original_value
nrv_value
write_down_amount
reversal_amount
assessment_date
```

---

# Inventory Services

## valuation_service.py

Functions:

```python
calculate_fifo_value()
calculate_weighted_average_value()
calculate_specific_identification_value()
calculate_nrv()
perform_lower_of_cost_or_nrv_test()
reverse_inventory_write_down()
```

---

## costing_service.py

Functions:

```python
calculate_fifo_cost()
calculate_weighted_average_cost()
calculate_standard_cost()
allocate_manufacturing_overheads()
calculate_batch_cost()
```

---

## inventory_posting_service.py

Functions:

```python
post_inventory_purchase()
post_inventory_sale()
post_stock_adjustment()
post_inventory_transfer()
post_inventory_return()
```

Purchase Flow:

```text
DR Inventory
CR Accounts Payable
```

Sales Flow:

```text
DR Accounts Receivable
CR Revenue

DR COGS
CR Inventory
```

---

# Multi-Currency Accounting

The system must support:

* Foreign supplier invoices
* Foreign customer invoices
* Historical exchange rates
* Forex gain/loss
* Unrealized forex adjustments

References:

* [https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/](https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/)

---

# Forex Accounting

Required Accounts:

```text
Forex Gain
Forex Loss
Unrealized Forex Gain
Unrealized Forex Loss
```

Required Service:

## forex_service.py

Functions:

```python
get_exchange_rate()
convert_currency()
convert_to_base_currency()
calculate_realized_forex_gain_loss()
calculate_unrealized_forex_gain_loss()
post_forex_adjustment()
```

---

# Receivable Accounting

## receivable_service.py

Functions:

```python
create_receivable_invoice()
allocate_customer_payment()
calculate_customer_aging()
post_bad_debt()
```

Support:

* Aging
* Credit notes
* Partial allocation
* Multi-currency invoices

---

# Payable Accounting

## payable_service.py

Functions:

```python
create_supplier_invoice()
allocate_supplier_payment()
calculate_supplier_aging()
post_expense_accrual()
```

Support:

* Supplier aging
* Accruals
* Partial settlements
* Multi-currency payables

---

# Rental Accounting

## rental_posting_service.py

Functions:

```python
post_rent_invoice()
post_rent_payment()
post_security_deposit()
post_rent_accrual()
```

Required Accounts:

```text
Rental Income
Deferred Rental Income
Security Deposit Liability
Late Fee Income
```

---

# SACCO Accounting

## sacco_posting_service.py

Functions:

```python
post_savings_deposit()
post_loan_disbursement()
post_loan_repayment()
post_interest_accrual()
post_penalty_charge()
```

Required Accounts:

```text
Member Savings
Loan Receivable
Interest Income
Interest Receivable
Penalty Income
Dividend Payable
```

---

# Asset Accounting

Support:

* Asset capitalization
* Depreciation
* Asset impairment
* Asset disposal
* Net Book Value tracking

## depreciation_service.py

Functions:

```python
generate_depreciation_schedule()
post_monthly_depreciation()
dispose_asset()
```

References:

* [https://www.ifrs.org/issued-standards/list-of-standards/ias-16-property-plant-and-equipment/](https://www.ifrs.org/issued-standards/list-of-standards/ias-16-property-plant-and-equipment/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ias-36-impairment-of-assets/](https://www.ifrs.org/issued-standards/list-of-standards/ias-36-impairment-of-assets/)

---

# Accrual Accounting

Support:

* Deferred revenue
* Deferred expenses
* Monthly accruals
* Reversing journals

## accrual_service.py

Functions:

```python
run_monthly_accruals()
reverse_accruals()
generate_accrual_schedule()
```

---

# Reconciliation Engine

## reconciliation_service.py

Functions:

```python
reconcile_control_accounts()
validate_subledger_integrity()
detect_out_of_balance_subledgers()
reconcile_bank_statement()
auto_match_transactions()
```

Must reconcile:

```text
AR Control == Customer Subledgers
AP Control == Supplier Subledgers
Inventory Control == Product/Warehouse Subledgers
```

---

# Utility Modules

Create:

```bash
utils/
```

Modules:

```bash
money.py
currency.py
ledger.py
reports.py
validators.py
inventory_costing.py
inventory_valuation.py
landed_costs.py
nrv.py
```

---

# Reporting Requirements

Reports:

* Balance Sheet
* Income Statement
* Cash Flow Statement
* Trial Balance
* General Ledger
* Inventory Valuation Report
* FIFO Layer Report
* Inventory Aging Report
* Manufacturing Variance Report
* Warehouse Valuation Report
* Forex Exposure Report
* AR Aging Report
* AP Aging Report

ALL reports must output UGX values.

---

# Posting Workflow Standard

Every posting workflow must:

```text
1. Validate input
2. Validate fiscal period
3. Fetch exchange rate
4. Convert to UGX
5. Create journal entry
6. Create journal lines
7. Validate balancing
8. Post immutable ledger entries
9. Update valuation layers
10. Emit audit log
```

---

# Audit Requirements

The system must support:

* Full audit trail
* Immutable ledger history
* Journal reversals
* Posting references
* User attribution
* Timestamp tracking
* Period locks
* Branch segregation

---

# Celery Jobs

Implement scheduled jobs for:

* Accrual runs
* Depreciation runs
* Inventory valuation recalculations
* NRV testing
* Forex revaluation
* Aging calculations
* Inventory provisioning

---

# Engineering Standards

Use:

* Django
* Django REST Framework
* PostgreSQL
* UUID primary keys
* Decimal money handling
* Typed Python
* Repository/query abstraction where useful
* Idempotent posting services
* transaction.atomic()

---

# DO NOT

```text
- Do NOT use Django signals for accounting posting
- Do NOT mutate historical ledger entries
- Do NOT allow unbalanced journals
- Do NOT put logic in models
- Do NOT put logic in serializers
- Do NOT support LIFO
- Do NOT recompute historical exchange rates
```

---

# Recommended Package Structure

```bash
accounting/
    models/
    services/
    repositories/
    selectors/
    utils/
    reports/
    tasks/
    api/
        serializers/
        views/
        routers/
    tests/
```

---

# Recommended References

IFRS Standards:

* [https://www.ifrs.org/](https://www.ifrs.org/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/](https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/](https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ias-16-property-plant-and-equipment/](https://www.ifrs.org/issued-standards/list-of-standards/ias-16-property-plant-and-equipment/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ias-36-impairment-of-assets/](https://www.ifrs.org/issued-standards/list-of-standards/ias-36-impairment-of-assets/)
* [https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/)

ERP Accounting Architecture:

* [https://learn.microsoft.com/en-us/dynamics365/finance/general-ledger/ledger-subledger](https://learn.microsoft.com/en-us/dynamics365/finance/general-ledger/ledger-subledger)
* [https://learn.microsoft.com/en-us/dynamics365/finance/general-ledger/](https://learn.microsoft.com/en-us/dynamics365/finance/general-ledger/)
* [https://help.sap.com/](https://help.sap.com/)
* [https://docs.oracle.com/en/applications/](https://docs.oracle.com/en/applications/)

Django:

* [https://docs.djangoproject.com/](https://docs.djangoproject.com/)
* [https://www.django-rest-framework.org/](https://www.django-rest-framework.org/)

PostgreSQL:

* [https://www.postgresql.org/docs/](https://www.postgresql.org/docs/)

Accounting References:

* [https://www.accountingcoach.com/](https://www.accountingcoach.com/)
* [https://corporatefinanceinstitute.com/](https://corporatefinanceinstitute.com/)
* [https://www.investopedia.com/](https://www.investopedia.com/)

---

# Final Goal

This skill should enable the complete implementation of:

* A production-grade ERP accounting engine
* IFRS-compliant accounting infrastructure
* Inventory accounting engine
* Manufacturing accounting engine
* Multi-currency accounting engine
* Subledger architecture
* Full financial reporting infrastructure
* Enterprise-grade audit-safe ledger system

The resulting architecture should resemble enterprise accounting systems such as:

* SAP ERP
* Oracle Financials
* Microsoft Dynamics 365 Finance
* Sage ERP
* Odoo Enterprise Accounting
