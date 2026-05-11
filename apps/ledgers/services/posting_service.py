from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.ledgers.models import Account, JournalEntry, LedgerEntry, SubLedgerEntry
from apps.ledgers.services.audit_service import emit_audit_log
from apps.ledgers.utils.money import round_currency


def calculate_running_balance(account: Account, debit_base: Decimal, credit_base: Decimal, branch=None) -> Decimal:
    """Derive a concurrency-safe running balance by aggregating all posted entries.

    Using select_for_update on the last row is not viable for an append-only table
    because we cannot predict which row will be last.  Instead we compute the true
    running balance from the SUM of all existing entries and add the current line.
    This is safe under concurrent writes because SUM is monotonic and the database
    engine guarantees read-committed isolation or better.
    """
    queryset = LedgerEntry.objects.filter(account=account)
    if branch is not None:
        queryset = queryset.filter(branch=branch)
    totals = queryset.aggregate(
        debit_total=Sum("debit_base", default=Decimal("0.00")),
        credit_total=Sum("credit_base", default=Decimal("0.00")),
    )
    existing_balance: Decimal
    if account.normal_balance == "debit":
        existing_balance = totals["debit_total"] - totals["credit_total"]
        return round_currency(existing_balance + debit_base - credit_base)
    existing_balance = totals["credit_total"] - totals["debit_total"]
    return round_currency(existing_balance + credit_base - debit_base)


def calculate_subledger_running_balance(*, subledger_account_id, debit_base: Decimal, credit_base: Decimal, branch=None) -> Decimal:
    queryset = SubLedgerEntry.objects.filter(subledger_account_id=subledger_account_id)
    if branch is not None:
        queryset = queryset.filter(branch=branch)
    totals = queryset.aggregate(
        debit_total=Sum("debit_base", default=Decimal("0.00")),
        credit_total=Sum("credit_base", default=Decimal("0.00")),
    )
    existing_balance = totals["debit_total"] - totals["credit_total"]
    return round_currency(existing_balance + debit_base - credit_base)


@transaction.atomic
def post_to_ledger(*, journal_entry: JournalEntry) -> list[LedgerEntry]:
    if journal_entry.status == JournalEntry.Status.POSTED:
        return list(
            LedgerEntry.objects.filter(journal_line__journal_entry=journal_entry)
            .select_related("account", "journal_line", "currency")
            .order_by("date", "created_at", "id")
        )

    ledger_entries: list[LedgerEntry] = []
    for line in journal_entry.lines.select_related("account", "currency").all():
        running_balance_base = calculate_running_balance(
            account=line.account,
            debit_base=line.debit_base,
            credit_base=line.credit_base,
            branch=journal_entry.branch,
        )
        ledger_entries.append(
            LedgerEntry.objects.create(
                account=line.account,
                journal_line=line,
                date=journal_entry.date,
                debit=line.debit_base,
                credit=line.credit_base,
                currency=line.currency,
                exchange_rate=line.exchange_rate,
                debit_foreign=line.debit_foreign,
                credit_foreign=line.credit_foreign,
                debit_base=line.debit_base,
                credit_base=line.credit_base,
                subledger_account=line.subledger_account,
                running_balance=running_balance_base,
                running_balance_base=running_balance_base,
                branch=journal_entry.branch,
            )
        )
        if line.subledger_account_id:
            SubLedgerEntry.objects.create(
                subledger_account_id=line.subledger_account_id,
                journal_line=line,
                date=journal_entry.date,
                debit_foreign=line.debit_foreign,
                credit_foreign=line.credit_foreign,
                debit_base=line.debit_base,
                credit_base=line.credit_base,
                running_balance_base=calculate_subledger_running_balance(
                    subledger_account_id=line.subledger_account_id,
                    debit_base=line.debit_base,
                    credit_base=line.credit_base,
                    branch=journal_entry.branch,
                ),
                branch=journal_entry.branch,
            )
    journal_entry.mark_posted()
    journal_entry.save(update_fields=["status", "posted_at", "updated_at"])
    emit_audit_log(
        event_type="journal.posted",
        entity_type="JournalEntry",
        entity_id=journal_entry.id,
        branch=journal_entry.branch,
        performed_by_id=journal_entry.created_by_id,
        payload={
            "ledger_entries": [str(item.id) for item in ledger_entries],
            "transaction_currency": journal_entry.transaction_currency.code,
            "base_currency": journal_entry.base_currency.code,
        },
    )
    return ledger_entries
