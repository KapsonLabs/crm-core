from __future__ import annotations

from datetime import date
from uuid import UUID

from django.db.models import QuerySet

from apps.ledgers.models import JournalEntry, LedgerEntry


class JournalRepository:
    @staticmethod
    def get(entry_id: UUID) -> JournalEntry:
        return JournalEntry.objects.prefetch_related("lines").get(pk=entry_id)

    @staticmethod
    def find_existing(
        source_module: str,
        source_id: str,
        idempotency_key: str,
    ) -> JournalEntry | None:
        if not idempotency_key:
            return None
        return JournalEntry.objects.filter(
            source_module=source_module,
            source_id=source_id,
            idempotency_key=idempotency_key,
        ).first()

    @staticmethod
    def posted_between(
        start_date: date,
        end_date: date,
        branch: UUID | None = None,
    ) -> QuerySet[JournalEntry]:
        queryset = JournalEntry.objects.filter(
            status=JournalEntry.Status.POSTED,
            date__range=(start_date, end_date),
        )
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        return queryset.order_by("date", "reference")

    @staticmethod
    def ledger_for_account(account_id: UUID, branch: UUID | None = None) -> QuerySet[LedgerEntry]:
        queryset = LedgerEntry.objects.filter(account_id=account_id)
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        return queryset.select_related("journal_line", "account").order_by("date", "created_at", "id")
