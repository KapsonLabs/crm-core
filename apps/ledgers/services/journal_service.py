from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.exceptions import AccountingError
from apps.ledgers.models import JournalEntry, JournalLine, SubLedgerAccount
from apps.ledgers.repositories.account_repository import AccountRepository
from apps.ledgers.repositories.journal_repository import JournalRepository
from apps.ledgers.services.audit_service import emit_audit_log
from apps.ledgers.services.posting_service import post_to_ledger
from apps.ledgers.services.types import JournalEntryInput, JournalLineInput
from apps.ledgers.utils.currency import get_exchange_rate
from apps.ledgers.utils.periods import ensure_date_in_open_period
from apps.ledgers.utils.validators import validate_account_active, validate_double_entry


def validate_journal_balance(lines: list[JournalLineInput]) -> None:
    validate_double_entry(lines)


def ensure_period_open(posting_date: date, branch):
    return ensure_date_in_open_period(posting_date=posting_date, branch=branch)


def _resolve_line_amounts(line: JournalLineInput, posting_date: date) -> tuple[Decimal, Decimal, Decimal, Decimal, str, Decimal]:
    rate = line.exchange_rate
    if rate == Decimal("1.000000") and line.currency_code != DEFAULT_CURRENCY:
        rate = get_exchange_rate(
            from_currency_code=line.currency_code,
            to_currency_code=DEFAULT_CURRENCY,
            rate_date=posting_date,
        )
    debit_foreign = line.debit_foreign
    credit_foreign = line.credit_foreign
    debit_base = line.debit_base
    credit_base = line.credit_base
    if line.currency_code == DEFAULT_CURRENCY:
        debit_base = debit_base or debit_foreign
        credit_base = credit_base or credit_foreign
        debit_foreign = debit_foreign or debit_base
        credit_foreign = credit_foreign or credit_base
    else:
        debit_base = debit_base or (debit_foreign * rate).quantize(Decimal("0.01"))
        credit_base = credit_base or (credit_foreign * rate).quantize(Decimal("0.01"))
    return debit_foreign, credit_foreign, debit_base, credit_base, line.currency_code, rate


@transaction.atomic
def create_journal_entry(
    *,
    entry_input: JournalEntryInput,
    line_inputs: list[JournalLineInput],
) -> JournalEntry:
    existing = JournalRepository.find_existing(
        source_module=entry_input.source_module,
        source_id=entry_input.source_id,
        idempotency_key=entry_input.idempotency_key,
    )
    if existing:
        return existing

    ensure_period_open(entry_input.date, entry_input.branch)
    prepared_lines = []
    for line in line_inputs:
        debit_foreign, credit_foreign, debit_base, credit_base, currency_code, rate = _resolve_line_amounts(
            line,
            entry_input.date,
        )
        prepared_lines.append(
            JournalLineInput(
                account_id=line.account_id,
                debit_foreign=debit_foreign,
                credit_foreign=credit_foreign,
                debit_base=debit_base,
                credit_base=credit_base,
                description=line.description,
                party_type=line.party_type,
                party_id=line.party_id,
                currency_code=currency_code,
                exchange_rate=rate,
                branch=line.branch,
                subledger_account_id=line.subledger_account_id,
            )
        )
    validate_journal_balance(prepared_lines)

    journal_entry = JournalEntry.objects.create(
        reference=entry_input.reference,
        journal_type=entry_input.journal_type,
        date=entry_input.date,
        description=entry_input.description,
        source_module=entry_input.source_module,
        source_id=entry_input.source_id,
        branch=entry_input.branch,
        created_by_id=entry_input.created_by_id,
        idempotency_key=entry_input.idempotency_key,
        extra_data=entry_input.extra_data,
        transaction_currency=AccountRepository.get_currency(entry_input.transaction_currency_code),
        exchange_rate=entry_input.exchange_rate
        if entry_input.transaction_currency_code == DEFAULT_CURRENCY
        else get_exchange_rate(
            from_currency_code=entry_input.transaction_currency_code,
            to_currency_code=entry_input.base_currency_code,
            rate_date=entry_input.date,
        ),
        base_currency=AccountRepository.get_currency(entry_input.base_currency_code),
    )

    accounts = {line.account_id: AccountRepository.get(line.account_id) for line in prepared_lines}
    subledgers = {
        line.subledger_account_id: SubLedgerAccount.objects.select_related("parent_control_account", "gl_account").get(pk=line.subledger_account_id)
        for line in prepared_lines
        if line.subledger_account_id
    }
    for line in prepared_lines:
        account = accounts[line.account_id]
        validate_account_active(account)
        subledger = subledgers.get(line.subledger_account_id) if line.subledger_account_id else None
        if account.is_control_account and subledger is None and not account.allows_manual_posting:
            raise AccountingError(f"Control account '{account.code}' requires a subledger reference.")
        if subledger and subledger.parent_control_account.gl_account_id != account.id:
            raise AccountingError(
                f"Subledger '{subledger.account_code}' does not belong to control account '{account.code}'."
            )
        JournalLine.objects.create(
            journal_entry=journal_entry,
            account=account,
            debit=line.debit_base,
            credit=line.credit_base,
            description=line.description,
            party_type=line.party_type,
            party_id=line.party_id,
            currency=AccountRepository.get_currency(line.currency_code),
            exchange_rate=line.exchange_rate,
            debit_foreign=line.debit_foreign,
            credit_foreign=line.credit_foreign,
            debit_base=line.debit_base,
            credit_base=line.credit_base,
            branch=journal_entry.branch,
            subledger_account=subledger,
        )

    emit_audit_log(
        event_type="journal.created",
        entity_type="JournalEntry",
        entity_id=journal_entry.id,
        branch=journal_entry.branch,
        performed_by_id=entry_input.created_by_id,
        payload={
            "reference": journal_entry.reference,
            "status": journal_entry.status,
            "transaction_currency": journal_entry.transaction_currency.code,
            "exchange_rate": str(journal_entry.exchange_rate),
            "base_currency": journal_entry.base_currency.code,
        },
    )
    return journal_entry


@transaction.atomic
def reverse_journal_entry(
    *,
    journal_entry_id: UUID,
    reversal_date,
    created_by_id: UUID | None = None,
    reason: str = "",
) -> JournalEntry:
    entry = JournalRepository.get(journal_entry_id)
    if entry.status != JournalEntry.Status.POSTED:
        raise AccountingError("Only posted journals can be reversed.")
    ensure_period_open(reversal_date, entry.branch)

    reversal = create_journal_entry(
        entry_input=JournalEntryInput(
            reference=f"{entry.reference}-REV",
            journal_type=f"{entry.journal_type}_reversal",
            date=reversal_date,
            description=reason or f"Reversal of {entry.reference}",
            source_module=entry.source_module,
            source_id=f"{entry.source_id}:reversal",
            branch=entry.branch,
            created_by_id=created_by_id,
            idempotency_key=f"reverse:{entry.id}",
            transaction_currency_code=entry.transaction_currency.code,
            exchange_rate=entry.exchange_rate,
            base_currency_code=entry.base_currency.code,
            extra_data={"reversed_entry_id": str(entry.id)},
        ),
        line_inputs=[
            JournalLineInput(
                account_id=line.account_id,
                debit_foreign=line.credit_foreign,
                credit_foreign=line.debit_foreign,
                debit_base=line.credit_base,
                credit_base=line.debit_base,
                description=f"Reversal of {line.description or entry.reference}",
                party_type=line.party_type,
                party_id=line.party_id,
                currency_code=line.currency.code,
                exchange_rate=line.exchange_rate,
                branch=line.branch,
                subledger_account_id=line.subledger_account_id,
            )
            for line in entry.lines.select_related("currency").all()
        ],
    )
    entry.reversed_entry = reversal
    entry.status = JournalEntry.Status.REVERSED
    entry.save(update_fields=["reversed_entry", "status", "updated_at"])
    emit_audit_log(
        event_type="journal.reversed",
        entity_type="JournalEntry",
        entity_id=entry.id,
        branch=entry.branch,
        performed_by_id=created_by_id,
        payload={"reversal_id": str(reversal.id)},
    )
    return reversal


@transaction.atomic
def post_journal_entry(*, journal_entry_id: UUID, performed_by_id: UUID | None = None) -> JournalEntry:
    journal_entry = JournalRepository.get(journal_entry_id)
    if journal_entry.status != JournalEntry.Status.DRAFT:
        if journal_entry.status == JournalEntry.Status.POSTED:
            return journal_entry
        raise AccountingError("Only draft journals can be posted.")
    validate_journal_balance(
        [
            JournalLineInput(
                account_id=line.account_id,
                debit_foreign=line.debit_foreign,
                credit_foreign=line.credit_foreign,
                debit_base=line.debit_base,
                credit_base=line.credit_base,
                description=line.description,
                party_type=line.party_type,
                party_id=line.party_id,
                currency_code=line.currency.code,
                exchange_rate=line.exchange_rate,
                branch=line.branch,
                subledger_account_id=line.subledger_account_id,
            )
            for line in journal_entry.lines.select_related("currency").all()
        ]
    )
    post_to_ledger(journal_entry=journal_entry)
    emit_audit_log(
        event_type="journal.posting_confirmed",
        entity_type="JournalEntry",
        entity_id=journal_entry.id,
        branch=journal_entry.branch,
        performed_by_id=performed_by_id,
        payload={"reference": journal_entry.reference},
    )
    return journal_entry
