from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.services.helpers import (
    build_two_line_entry,
    create_and_post_journal,
    get_configured_account,
)
from apps.ledgers.services.journal_service import reverse_journal_entry
from apps.ledgers.services.receivable_service import create_receivable_invoice
from apps.ledgers.services.types import JournalLineInput

logger = logging.getLogger(__name__)


@transaction.atomic
def post_customer_invoice(invoice) -> object:
    if invoice.status == "void":
        raise ValueError("Cannot post a voided invoice.")
    if invoice.total <= Decimal("0.00"):
        raise ValueError("Invoice total must be positive.")

    customer = invoice.job.customer
    branch_id = invoice.branch_id
    revenue_account = get_configured_account("revenue", branch_id)

    if invoice.tax_amount > Decimal("0.00"):
        return _post_invoice_with_tax(invoice, customer, revenue_account, branch_id)

    return create_receivable_invoice(
        invoice_id=str(invoice.invoice_number),
        posting_date=invoice.issued_at,
        amount=invoice.total,
        revenue_account_id=revenue_account.id,
        customer_id=str(customer.id),
        branch=branch_id,
        created_by_id=invoice.created_by_id,
        currency=invoice.currency,
    )


def _post_invoice_with_tax(invoice, customer, revenue_account, branch_id):
    receivable = get_configured_account("accounts_receivable", branch_id)
    vat_output = get_configured_account("vat_output_control", branch_id)

    lines = [
        JournalLineInput(
            account_id=receivable.id,
            debit_foreign=invoice.total,
            debit_base=Decimal("0.00"),
            currency_code=invoice.currency,
            description=f"Customer invoice {invoice.invoice_number}",
            branch=branch_id,
            party_type="customer",
            party_id=str(customer.id),
        ),
        JournalLineInput(
            account_id=revenue_account.id,
            credit_foreign=invoice.subtotal,
            credit_base=Decimal("0.00"),
            currency_code=invoice.currency,
            description=f"Revenue – {invoice.invoice_number}",
            branch=branch_id,
            party_type="customer",
            party_id=str(customer.id),
        ),
        JournalLineInput(
            account_id=vat_output.id,
            credit_foreign=invoice.tax_amount,
            credit_base=Decimal("0.00"),
            currency_code=invoice.currency,
            description=f"VAT output – {invoice.invoice_number}",
            branch=branch_id,
            party_type="customer",
            party_id=str(customer.id),
        ),
    ]

    return create_and_post_journal(
        reference=f"AR-{invoice.invoice_number}",
        journal_type="receivable_invoice",
        posting_date=invoice.issued_at,
        description=f"Customer invoice {invoice.invoice_number} (with VAT)",
        source_module="receivables",
        source_id=str(invoice.invoice_number),
        branch=branch_id,
        created_by_id=invoice.created_by_id,
        idempotency_key=f"customer-invoice:{invoice.invoice_number}",
        lines=lines,
        transaction_currency_code=invoice.currency,
    )


@transaction.atomic
def reverse_customer_invoice(
    invoice,
    *,
    reversal_date: date,
    created_by_id: UUID | None = None,
    reason: str = "",
) -> object:
    from apps.ledgers.repositories.journal_repository import JournalRepository

    journal = JournalRepository.find_existing(
        source_module="receivables",
        source_id=str(invoice.invoice_number),
        idempotency_key=f"customer-invoice:{invoice.invoice_number}",
    )
    if not journal:
        journal = JournalRepository.find_existing(
            source_module="receivables",
            source_id=str(invoice.invoice_number),
            idempotency_key=f"receivable-invoice:{invoice.invoice_number}",
        )
    if not journal:
        raise ValueError(f"No posted journal found for invoice {invoice.invoice_number}.")

    return reverse_journal_entry(
        journal_entry_id=journal.id,
        reversal_date=reversal_date,
        created_by_id=created_by_id,
        reason=reason or f"Reversal of customer invoice {invoice.invoice_number}",
    )
