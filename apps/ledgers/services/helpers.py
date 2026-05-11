from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.exceptions import PostingConfigurationError
from apps.ledgers.models import JournalEntry
from apps.ledgers.repositories.account_repository import AccountRepository
from apps.ledgers.services.journal_service import create_journal_entry
from apps.ledgers.services.posting_service import post_to_ledger
from apps.ledgers.services.types import JournalEntryInput, JournalLineInput


def get_configured_account(account_key: str, branch: UUID | None):
    config = AccountRepository.get_configuration(branch=branch)
    code = config.default_accounts.get(account_key)
    if not code:
        raise PostingConfigurationError(f"Missing configured account mapping for '{account_key}'.")
    return AccountRepository.get_by_code(code=code, branch=branch)


@transaction.atomic
def create_and_post_journal(
    *,
    reference: str,
    journal_type: str,
    posting_date: date,
    description: str,
    source_module: str,
    source_id: str,
    branch: UUID | None,
    created_by_id: UUID | None,
    lines: list[JournalLineInput],
    idempotency_key: str,
    extra_data: dict | None = None,
    transaction_currency_code: str = DEFAULT_CURRENCY,
) -> JournalEntry:
    effective_transaction_currency = transaction_currency_code
    if effective_transaction_currency == DEFAULT_CURRENCY and lines:
        effective_transaction_currency = lines[0].currency_code
    entry = create_journal_entry(
        entry_input=JournalEntryInput(
            reference=reference,
            journal_type=journal_type,
            date=posting_date,
            description=description,
            source_module=source_module,
            source_id=source_id,
            branch=branch,
            created_by_id=created_by_id,
            idempotency_key=idempotency_key,
            transaction_currency_code=effective_transaction_currency,
            base_currency_code=DEFAULT_CURRENCY,
            extra_data=extra_data or {},
        ),
        line_inputs=lines,
    )
    if entry.status != JournalEntry.Status.POSTED:
        post_to_ledger(journal_entry=entry)
    return entry


def build_two_line_entry(
    *,
    debit_account_id: UUID,
    credit_account_id: UUID,
    amount: Decimal,
    currency: str,
    description: str,
    branch: UUID | None,
    party_type: str = "",
    party_id: str = "",
    exchange_rate: Decimal | None = None,
    rate_date: date | None = None,
    debit_subledger_account_id: UUID | None = None,
    credit_subledger_account_id: UUID | None = None,
) -> list[JournalLineInput]:
    rate = exchange_rate or Decimal("1.000000")
    if currency == DEFAULT_CURRENCY:
        base_amount = amount
    elif exchange_rate is not None:
        base_amount = (amount * rate).quantize(Decimal("1"))
    else:
        base_amount = Decimal("0.00")
    return [
        JournalLineInput(
            account_id=debit_account_id,
            debit_foreign=amount,
            debit_base=base_amount,
            currency_code=currency,
            exchange_rate=rate,
            description=description,
            branch=branch,
            party_type=party_type,
            party_id=party_id,
            subledger_account_id=debit_subledger_account_id,
        ),
        JournalLineInput(
            account_id=credit_account_id,
            credit_foreign=amount,
            credit_base=base_amount,
            currency_code=currency,
            exchange_rate=rate,
            description=description,
            branch=branch,
            party_type=party_type,
            party_id=party_id,
            subledger_account_id=credit_subledger_account_id,
        ),
    ]
