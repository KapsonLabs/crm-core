from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.services.helpers import (
    create_and_post_journal,
    get_configured_account,
)
from apps.ledgers.services.journal_service import reverse_journal_entry
from apps.ledgers.services.payable_service import create_supplier_invoice
from apps.ledgers.services.types import JournalLineInput

logger = logging.getLogger(__name__)


@transaction.atomic
def post_supplier_invoice(lpo) -> object:
    if lpo.status == "cancelled":
        raise ValueError("Cannot post a cancelled LPO.")
    if lpo.total <= Decimal("0.00"):
        raise ValueError("LPO total must be positive.")

    supplier = lpo.supplier
    branch_id = lpo.branch_id
    expense_account = get_configured_account("purchase_expense", branch_id)

    posting_date = lpo.delivered_at
    if posting_date is None:
        posting_date = date.today()
    if hasattr(posting_date, "date"):
        posting_date = posting_date.date()

    return create_supplier_invoice(
        invoice_id=str(lpo.lpo_number or lpo.id),
        posting_date=posting_date,
        amount=lpo.total,
        expense_account_id=expense_account.id,
        supplier_id=str(supplier.id),
        branch=branch_id,
        created_by_id=lpo.created_by_id,
        currency=lpo.currency,
    )


@transaction.atomic
def post_supplier_invoice_with_tax(
    lpo,
    *,
    net_amount: Decimal,
    tax_amount: Decimal,
) -> object:
    if lpo.status == "cancelled":
        raise ValueError("Cannot post a cancelled LPO.")

    supplier = lpo.supplier
    branch_id = lpo.branch_id
    expense_account = get_configured_account("purchase_expense", branch_id)
    payable = get_configured_account("accounts_payable", branch_id)
    vat_input = get_configured_account("vat_input_control", branch_id)

    posting_date = lpo.delivered_at
    if posting_date is None:
        posting_date = date.today()
    if hasattr(posting_date, "date"):
        posting_date = posting_date.date()

    total = net_amount + tax_amount
    invoice_ref = str(lpo.lpo_number or lpo.id)

    lines = [
        JournalLineInput(
            account_id=expense_account.id,
            debit_foreign=net_amount,
            debit_base=Decimal("0.00"),
            currency_code=lpo.currency,
            description=f"Expense – {invoice_ref}",
            branch=branch_id,
            party_type="supplier",
            party_id=str(supplier.id),
        ),
        JournalLineInput(
            account_id=vat_input.id,
            debit_foreign=tax_amount,
            debit_base=Decimal("0.00"),
            currency_code=lpo.currency,
            description=f"VAT input – {invoice_ref}",
            branch=branch_id,
            party_type="supplier",
            party_id=str(supplier.id),
        ),
        JournalLineInput(
            account_id=payable.id,
            credit_foreign=total,
            credit_base=Decimal("0.00"),
            currency_code=lpo.currency,
            description=f"Supplier invoice {invoice_ref}",
            branch=branch_id,
            party_type="supplier",
            party_id=str(supplier.id),
        ),
    ]

    return create_and_post_journal(
        reference=f"AP-{invoice_ref}",
        journal_type="supplier_invoice",
        posting_date=posting_date,
        description=f"Supplier invoice {invoice_ref} (with VAT)",
        source_module="payables",
        source_id=invoice_ref,
        branch=branch_id,
        created_by_id=lpo.created_by_id,
        idempotency_key=f"supplier-invoice:{invoice_ref}",
        lines=lines,
        transaction_currency_code=lpo.currency,
    )


@transaction.atomic
def reverse_supplier_invoice(
    lpo,
    *,
    reversal_date: date,
    created_by_id: UUID | None = None,
    reason: str = "",
) -> object:
    from apps.ledgers.repositories.journal_repository import JournalRepository

    invoice_ref = str(lpo.lpo_number or lpo.id)
    journal = JournalRepository.find_existing(
        source_module="payables",
        source_id=invoice_ref,
        idempotency_key=f"supplier-invoice:{invoice_ref}",
    )
    if not journal:
        raise ValueError(f"No posted journal found for supplier invoice {invoice_ref}.")

    return reverse_journal_entry(
        journal_entry_id=journal.id,
        reversal_date=reversal_date,
        created_by_id=created_by_id,
        reason=reason or f"Reversal of supplier invoice {invoice_ref}",
    )
