from __future__ import annotations

from typing import Iterable
from uuid import UUID

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.models import Account, AccountingConfiguration, Currency, ExchangeRate


class AccountRepository:
    @staticmethod
    def get(account_id: UUID) -> Account:
        return Account.objects.get(pk=account_id)

    @staticmethod
    def get_by_code(code: str, branch: UUID | None = None) -> Account:
        if branch is not None:
            account = Account.objects.filter(code=code, branch=branch).first()
            if account:
                return account
            # Fall back to the global (branch-agnostic) account
            return Account.objects.filter(code=code, branch__isnull=True).get()
        return Account.objects.filter(code=code, branch__isnull=True).get()

    @staticmethod
    def list_postable(branch: UUID | None = None) -> Iterable[Account]:
        queryset = Account.objects.filter(is_active=True)
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        return queryset.order_by("code")

    @staticmethod
    def get_configuration(branch: UUID | None = None) -> AccountingConfiguration:
        if branch is not None:
            config = AccountingConfiguration.objects.filter(branch=branch).first()
            if config:
                return config
        return AccountingConfiguration.objects.get(branch__isnull=True)

    @staticmethod
    def get_currency(code: str) -> Currency:
        return Currency.objects.get(code=code, is_active=True)

    @staticmethod
    def get_base_currency() -> Currency:
        return Currency.objects.get(code=DEFAULT_CURRENCY, is_base_currency=True)

    @staticmethod
    def latest_exchange_rate(from_currency_code: str, to_currency_code: str, rate_date) -> ExchangeRate | None:
        return (
            ExchangeRate.objects.filter(
                from_currency__code=from_currency_code,
                to_currency__code=to_currency_code,
                date__lte=rate_date,
            )
            .order_by("-date", "-created_at")
            .first()
        )
