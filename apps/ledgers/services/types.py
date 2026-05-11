from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from apps.ledgers.constants import DEFAULT_CURRENCY, DEFAULT_EXCHANGE_RATE


@dataclass(frozen=True)
class JournalLineInput:
    account_id: UUID
    debit_foreign: Decimal = Decimal("0.00")
    credit_foreign: Decimal = Decimal("0.00")
    debit_base: Decimal = Decimal("0.00")
    credit_base: Decimal = Decimal("0.00")
    description: str = ""
    party_type: str = ""
    party_id: str = ""
    currency_code: str = DEFAULT_CURRENCY
    exchange_rate: Decimal = DEFAULT_EXCHANGE_RATE
    branch: UUID | None = None
    subledger_account_id: UUID | None = None


@dataclass(frozen=True)
class JournalEntryInput:
    reference: str
    journal_type: str
    date: date
    description: str
    source_module: str
    source_id: str
    branch: UUID | None
    created_by_id: UUID | None = None
    idempotency_key: str = ""
    transaction_currency_code: str = DEFAULT_CURRENCY
    exchange_rate: Decimal = DEFAULT_EXCHANGE_RATE
    base_currency_code: str = DEFAULT_CURRENCY
    extra_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BankStatementLine:
    reference: str
    amount: Decimal
    transaction_date: date
    narrative: str = ""
