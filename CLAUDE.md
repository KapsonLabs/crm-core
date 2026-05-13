# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test apps.financials
python manage.py test apps.suppliers

# Run a single test class or method
python manage.py test apps.financials.tests.test_accounting_integration.InvoiceAccountingPostingTest
python manage.py test apps.suppliers.tests.test_lpo_lifecycle.SuppliersLPOLifecycleTests.test_lpo_full_lifecycle

# Apply migrations
python manage.py migrate

# Create migrations after model changes
python manage.py makemigrations

# Run the dev server
python manage.py runserver

# Start Celery worker
celery -A crm worker --loglevel=info

# Run ASGI server (for WebSockets)
daphne crm.asgi:application
```

Requires a `.env` file at the project root with: `SECRET_KEY`, `ALLOWED_HOSTS`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `LANGUAGE_CODE`, `TIME_ZONE`. Redis must be running on `localhost:6379` for Channels and Celery.

## Architecture

### Multi-tenant scoping

Every operational record belongs to an `Organization` (top-level tenant) and optionally a `Branch`. The custom `User` model (`apps.accounts.User`, extends `AbstractUser`) carries `organization` and `branch` FKs. All service functions receive a `user` argument and filter querysets to the user's visible scope — this is the primary access-control mechanism, not DRF permissions alone.

`user.is_job_manager` returns `True` for superusers, staff, or users with a Supervisor/Manager role. Most write operations are gated on this property.

### Service layer pattern

Business logic lives exclusively in `services.py` (or `services/` package) within each app. Views deserialise input, call a service function, and return the result. **Never put business logic in serializers, models, or views.** Service functions that write to the database must be wrapped in `@transaction.atomic`.

### Ledgers accounting engine (`apps/ledgers`)

The `ledgers` app is an immutable double-entry accounting engine. Key rules:
- All posting goes through `apps.ledgers.services.helpers.create_and_post_journal()` or a specialised service (`receivable_service`, `payable_service`, etc.).
- **Never create `LedgerEntry` or `SubLedgerEntry` rows directly.**
- **Never use Django signals** for accounting events.
- All monetary values use `Decimal`. Never use `float`.
- Base currency is `UGX` (`apps.ledgers.constants.DEFAULT_CURRENCY`). Foreign currency transactions store both the source amount and the UGX equivalent. Historical exchange rates must never be recomputed.
- Account lookups use `get_configured_account(key, branch)` — account codes come from `AccountingConfiguration.default_accounts` (a JSON field), never hardcoded.
- `JournalEntry.idempotency_key` prevents duplicate postings. Format: `"{module}-{entity-type}:{id}"` e.g. `"customer-invoice:INV-20260509-0001"`.
- Cancellations and voids create reversal journals via `reverse_journal_entry()`. Posted journals are never mutated.
- Subledgers are created via `create_default_entity_accounts(EntitySubledgerRequest(...))` — one call per entity type creates all relevant sub-ledgers automatically.

### Accounting integration points

Operational modules integrate with the ledgers engine through thin service files under each app's `services/` package:

| Trigger | Service file | Engine call |
|---|---|---|
| Customer created | `customers/services/customer_accounting_service.py` | `create_default_entity_accounts(entity_type="customer")` |
| Supplier created | `suppliers/services/supplier_accounting_service.py` | `create_default_entity_accounts(entity_type="supplier")` |
| Invoice created (non-draft) | `financials/services/invoice_accounting_service.py` | `receivable_service.create_receivable_invoice()` |
| Invoice voided | `financials/services/invoice_accounting_service.py` | `reverse_journal_entry()` |
| Payment recorded | `financials/services/customer_payment_accounting_service.py` | `receivable_service.allocate_customer_payment()` |
| Payment deleted | `financials/services/customer_payment_accounting_service.py` | `reverse_journal_entry()` |
| LPO marked received | `suppliers/services/supplier_invoice_accounting_service.py` | `payable_service.create_supplier_invoice()` |
| LPO cancelled | `suppliers/services/supplier_invoice_accounting_service.py` | `reverse_journal_entry()` |

### App responsibilities

- **`accounts`** — custom `User`, `Role`, `Permission`, `Module` models; JWT auth; `IsJobManager` permission class.
- **`organization`** — `Organization`, `Branch`, `BranchSettings`; `resolve_branch_for_user()` utility used by all create-service functions.
- **`customers`** — `Customer`, `CustomerFeedback`; scoped by org/branch.
- **`suppliers`** — `Supplier`, `LocalPurchaseOrder`, `LocalPurchaseOrderItem`; full LPO lifecycle (draft → issued → in_transit → received / cancelled).
- **`financials`** — `Invoice`, `InvoicePayment`, `Requisition`; invoice number auto-generated as `INV-YYYYMMDD-NNNN`.
- **`jobs`** — `Job`, `Product`, `JobAssignment`; a Job belongs to a Customer and is the foreign key Invoice hangs off.
- **`ledgers`** — accounting engine (see above).
- **`expense_accounting`** — expense transactions, approvals, prepaid schedules; posts to ledgers via `expense_posting_service`.
- **`kpis`** — KPI definitions, entries, assignments, reports; includes a versioned execution engine under `kpis/domain/`.
- **`crm`** — tickets, notifications, in-app messages; uses Django Channels for real-time delivery.
- **`analytics`** — read-only aggregate views over jobs/invoices/customers.
- **`info`** — reference data: categories, tags, FAQs, SOPs, policy explanations, training articles.

### API conventions

- All endpoints live under `/api/{app}/`.
- Views are class-based (`APIView`), never `ModelViewSet`.
- Response envelope: `{"status": 200, "data": ...}` for success; `{"status": 400, "message": "..."}` for errors.
- Authentication: JWT Bearer token (`Authorization: Bearer <token>`). Obtain via `POST /api/accounts/auth/login/`.
- All primary keys are UUIDs. URL patterns use `<uuid:pk>`.

### Testing conventions

Tests use `APITestCase` with `setUpTestData` for fixtures and `force_authenticate` for auth. Tests that cover accounting integration mock the ledger engine calls (`patch("apps.xxx.services.yyy_service.create_and_post_journal")` etc.) so they don't require a configured `AccountingConfiguration` in the test database.
