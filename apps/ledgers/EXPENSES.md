# Expense Accounting Engine — Skill.md

## Overview

This skill defines the complete architecture, accounting workflows, posting logic, approval systems, budgeting integrations, reimbursement handling, prepaid expense accounting, accrual accounting, and IFRS-compliant expense accounting infrastructure required for a production-grade Django ERP system.

This module extends the ERP accounting engine into a fully operational enterprise expense management system comparable to:

* SAP ERP
* Oracle Financials
* Microsoft Dynamics 365 Finance
* Sage ERP
* Odoo Enterprise Accounting

The expense engine must support:

* Operational expenses
* Supplier expenses
* Employee reimbursements
* Expense accruals
* Prepaid expenses
* Budget enforcement
* Multi-level approvals
* Tax/VAT handling
* Multi-currency expense accounting
* Cost-center accounting
* Department accounting
* Project expense accounting
* Corporate card accounting
* Expense amortization
* Branch expense accounting

---

# Core Philosophy

Expenses in ERP systems are NOT merely journal entries.

Expenses are operational financial events that:

* require approvals,
* affect budgets,
* affect profitability,
* affect taxation,
* may become assets,
* may become prepaid expenses,
* may require amortization,
* may belong to projects,
* may belong to departments,
* may require reimbursements.

This module must therefore function as:

* an accounting engine,
* an operational workflow engine,
* and a financial control system.

---

# Architectural Principles

## 1. Service Layer Architecture

ALL expense accounting logic must exist in:

```bash
services/
```

Example:

```bash
expense_accounting/
    services/
        expense_posting_service.py
        reimbursement_service.py
        prepaid_expense_service.py
        expense_allocation_service.py
        expense_budget_service.py
        expense_tax_service.py
        expense_approval_service.py
```

NEVER:

* Put expense logic in models
* Put accounting logic in serializers
* Use signals for accounting posting

---

## 2. Immutable Ledger Design

Ledger entries must:

* be append-only,
* never be mutated,
* never be deleted.

Corrections must occur via:

* reversal journals,
* adjustment journals.

---

## 3. Transaction Safety

ALL posting workflows must use:

```python
transaction.atomic()
```

---

# IFRS / IAS Standards To Implement

The expense engine must align with:

## Core Standards

* IAS 1 — Presentation of Financial Statements
* IAS 16 — Property, Plant and Equipment
* IAS 21 — Foreign Exchange Effects
* IAS 23 — Borrowing Costs
* IAS 36 — Impairment of Assets
* IFRS 15 — Revenue from Contracts with Customers

References:

[IAS 1 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ias-1-presentation-of-financial-statements/?utm_source=chatgpt.com)

[IAS 16 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ias-16-property-plant-and-equipment/?utm_source=chatgpt.com)

[IAS 21 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/?utm_source=chatgpt.com)

[IAS 23 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ias-23-borrowing-costs/?utm_source=chatgpt.com)

[IAS 36 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ias-36-impairment-of-assets/?utm_source=chatgpt.com)

[IFRS 15 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/?utm_source=chatgpt.com)

---

# Expense Accounting Domains

The engine must support:

1. Direct Operational Expenses
2. Supplier Bills
3. Employee Reimbursements
4. Prepaid Expenses
5. Accrued Expenses
6. Deferred Expenses
7. Project Expenses
8. Departmental Expenses
9. Manufacturing Overhead Expenses
10. Branch Expenses
11. Capitalizable Expenses
12. Expense Allocations
13. Corporate Card Expenses
14. Expense Claims
15. Budget-Controlled Expenses

---

# Operational Expense Accounting

Examples:

* Utilities
* Fuel
* Internet
* Cleaning
* Rent
* Security
* Stationery
* Repairs

Posting:

```text
DR Expense
CR Accounts Payable/Cash
```

---

# Supplier Expense Accounting

Supplier invoices must support:

* AP integration
* VAT
* withholding tax
* accruals
* partial settlement
* multi-currency billing

Posting:

```text
DR Expense
DR VAT Input
CR Accounts Payable
```

---

# Employee Reimbursement Accounting

Support:

* travel reimbursements
* meal reimbursements
* fuel claims
* accommodation claims
* petty cash claims

Workflow:

1. Employee submits claim
2. Manager approval
3. Finance approval
4. Reimbursement posting

Posting:

```text
DR Travel Expense
CR Employee Reimbursement Liability
```

Settlement:

```text
DR Employee Reimbursement Liability
CR Cash/Bank
```

---

# Prepaid Expense Accounting

Examples:

* annual insurance
* annual rent
* annual software subscriptions

Initial Posting:

```text
DR Prepaid Expense Asset
CR Cash/AP
```

Monthly Amortization:

```text
DR Expense
CR Prepaid Expense Asset
```

Support:

* amortization schedules
* recurring journal automation
* reversal handling

---

# Accrued Expense Accounting

Examples:

* accrued payroll
* accrued utilities
* accrued interest
* accrued rent

Month-end Posting:

```text
DR Expense
CR Accrued Expense Liability
```

Reversal:

```text
DR Accrued Expense Liability
CR Expense
```

---

# Capitalizable Expense Accounting

Some expenses MUST become assets.

Examples:

* machinery installation
* import duty
* building improvements
* transportation of equipment

Correct Posting:

```text
DR Fixed Asset
CR AP/Cash
```

NOT:

```text
DR Expense
```

Critical IFRS Requirement:
IAS 16 — Property, Plant and Equipment

---

# Project and Job Expense Accounting

Support:

* project expense accumulation
* construction accounting
* manufacturing overhead allocation
* WIP capitalization
* profitability analysis

Required:

* project-level expense ledgers
* project allocation engine
* cost-center accounting

---

# Expense Budgeting

Support:

* departmental budgets
* project budgets
* branch budgets
* category budgets

Capabilities:

* budget availability checks
* over-budget prevention
* budget variance analysis

---

# Required Models

ONLY accounting-supporting models.

---

## ExpenseCategory

Defines accounting behavior.

Fields:

```python
name
expense_type
default_expense_account
default_tax_account
requires_approval
is_capitalizable
is_prepaid_eligible
requires_project
requires_department
is_active
```

---

## ExpenseTransaction

Represents operational expense.

Fields:

```python
reference
expense_category
vendor
employee
branch
department
project
cost_center
currency
exchange_rate
amount
base_amount
tax_amount
description
expense_date
status
approval_status
payment_status
created_by
approved_by
posted_at
```

Statuses:

```text
draft
submitted
approved
posted
rejected
paid
cancelled
```

---

## ExpenseLine

Fields:

```python
expense_transaction
expense_account
amount
tax_amount
department
project
cost_center
description
```

---

## ExpenseApproval

Fields:

```python
expense_transaction
approver
approval_level
status
approved_at
remarks
```

---

## PrepaidExpenseSchedule

Fields:

```python
expense_transaction
start_date
end_date
monthly_amount
remaining_balance
next_run_date
status
```

---

## ExpenseBudget

Fields:

```python
fiscal_period
department
project
branch
expense_category
budget_amount
consumed_amount
remaining_amount
```

---

## CorporateCardTransaction

Fields:

```python
card_reference
employee
expense_transaction
transaction_date
amount
currency
merchant
reconciled
```

---

# Required Services

---

## expense_posting_service.py

Responsibilities:

* expense posting
* approval workflows
* reimbursement handling
* journal creation
* tax posting

Functions:

```python
create_expense()
submit_expense()
approve_expense()
reject_expense()
post_expense()
pay_expense()
reverse_expense()
```

---

## reimbursement_service.py

Functions:

```python
submit_employee_claim()
approve_claim()
reject_claim()
reimburse_employee()
```

---

## prepaid_expense_service.py

Functions:

```python
create_prepaid_schedule()
amortize_prepaid_expense()
reverse_prepaid_expense()
```

---

## expense_allocation_service.py

Responsibilities:

* cost-center allocation
* department allocation
* branch allocation
* project allocation

Functions:

```python
allocate_expense()
split_expense_by_percentage()
allocate_to_project()
allocate_to_departments()
allocate_to_branches()
```

---

## expense_budget_service.py

Functions:

```python
check_budget_availability()
consume_budget()
release_budget()
generate_budget_variance()
```

---

## expense_tax_service.py

Responsibilities:

* VAT calculations
* withholding tax
* tax-inclusive calculations
* tax-exclusive calculations

Functions:

```python
calculate_input_vat()
calculate_withholding_tax()
split_tax_amounts()
```

---

## expense_approval_service.py

Functions:

```python
determine_approval_level()
route_for_approval()
approve_expense()
reject_expense()
escalate_pending_approval()
```

---

# Approval Workflow Engine

Support:

* multi-level approvals
* threshold-based approvals
* finance approvals
* department approvals
* escalations

Example:

```text
0 - 500,000 UGX
    -> manager approval

500,000 - 5,000,000 UGX
    -> finance approval

Above 5,000,000 UGX
    -> CFO approval
```

---

# Multi-Currency Expense Accounting

The system must support:

* foreign supplier invoices
* foreign reimbursements
* historical exchange rates
* forex gain/loss accounting

Requirements:

* preserve transaction currency
* preserve exchange rate used
* store UGX-equivalent base values

ALL official reports must output UGX values.

---

# Tax/VAT Accounting

Support:

* VAT input
* withholding tax
* tax-inclusive invoices
* tax-exclusive invoices

Posting Example:

```text
DR Expense
DR VAT Input
CR Accounts Payable
```

---

# Auto Ledger Creation

The following should auto-create ledgers.

## Expense Categories

Examples:

* Fuel Expense
* Utilities Expense
* Internet Expense
* Travel Expense
* Repairs Expense

Each category should generate:

* Expense Ledger
* Accrual Ledger
* Prepaid Ledger (optional)

---

## Departments

Auto-create:

* Department Expense Ledger

---

## Projects

Auto-create:

* Project Expense Ledger
* Project WIP Ledger

---

## Employees

Auto-create:

* Employee Reimbursement Ledger

---

# ERP Integration Points

Expense accounting integrates with:

| Module           | Integration         |
| ---------------- | ------------------- |
| Accounts Payable | supplier expenses   |
| Banking          | payments            |
| Payroll          | reimbursements      |
| Inventory        | consumables         |
| Assets           | capitalization      |
| Projects         | job costing         |
| Manufacturing    | overhead allocation |
| Tax              | VAT/WHT             |
| Budgeting        | expense controls    |

---

# Reporting Requirements

Implement:

## Expense Reports

* Expense Analysis
* Department Expense Report
* Project Expense Report
* Budget Variance Report
* Prepaid Expense Report
* Expense Aging
* Employee Claims Report
* Expense Trend Analysis
* Branch Expense Analysis
* Corporate Card Usage Report
* Tax Deduction Report

ALL reports must support:

* branch filtering
* project filtering
* department filtering
* period filtering
* UGX base reporting

---

# Celery Scheduled Jobs

Implement scheduled tasks for:

* prepaid amortization
* accrual reversals
* recurring expenses
* approval escalations
* budget monitoring
* reimbursement reminders

---

# Utility Modules

Create:

```bash
utils/
```

Modules:

```bash
expense_tax.py
expense_allocations.py
budgeting.py
expense_reporting.py
prepaid_calculations.py
```

---

# Audit Requirements

The system must support:

* immutable expense journals
* full audit trail
* approval history
* user attribution
* posting references
* timestamp tracking
* reversal tracking

---

# Engineering Standards

Use:

* Django
* Django REST Framework
* PostgreSQL
* UUID primary keys
* Decimal money handling
* Typed Python
* Repository/query abstraction
* transaction.atomic()
* Idempotent posting services

---

# DO NOT

```text
- Do NOT use signals for expense posting
- Do NOT mutate historical ledger entries
- Do NOT allow unbalanced journals
- Do NOT use float money values
- Do NOT place accounting logic in models
- Do NOT place business logic in serializers
```

---

# Recommended Package Structure

```bash
expense_accounting/
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

[IFRS Official Website](https://www.ifrs.org/?utm_source=chatgpt.com)

[IAS 1 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ias-1-presentation-of-financial-statements/?utm_source=chatgpt.com)

[IAS 16 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ias-16-property-plant-and-equipment/?utm_source=chatgpt.com)

[IAS 21 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/?utm_source=chatgpt.com)

[IAS 23 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ias-23-borrowing-costs/?utm_source=chatgpt.com)

[IAS 36 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ias-36-impairment-of-assets/?utm_source=chatgpt.com)

[IFRS 15 Reference](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/?utm_source=chatgpt.com)

ERP Accounting Architecture:

[Microsoft Dynamics Finance Architecture](https://learn.microsoft.com/en-us/dynamics365/finance/?utm_source=chatgpt.com)

[SAP Help Portal](https://help.sap.com/?utm_source=chatgpt.com)

[Oracle Financials Documentation](https://docs.oracle.com/en/applications/?utm_source=chatgpt.com)

Django:

[Django Documentation](https://docs.djangoproject.com/?utm_source=chatgpt.com)

[Django REST Framework Documentation](https://www.django-rest-framework.org/?utm_source=chatgpt.com)

PostgreSQL:

[PostgreSQL Documentation](https://www.postgresql.org/docs/?utm_source=chatgpt.com)

---

# Final Goal

This skill should enable the implementation of:

* enterprise-grade expense accounting,
* operational expense workflows,
* ERP approval infrastructure,
* IFRS-compliant expense accounting,
* multi-currency expense management,
* reimbursement management,
* prepaid/amortization accounting,
* branch/project/cost-center accounting,
* audit-safe expense posting,
* scalable budgeting infrastructure.

The resulting architecture should be comparable to enterprise ERP accounting systems used in:

* SAP ERP
* Oracle Financials
* Microsoft Dynamics 365 Finance
* Sage ERP
* Odoo Enterprise Accounting
