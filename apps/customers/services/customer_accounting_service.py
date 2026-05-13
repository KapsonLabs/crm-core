from __future__ import annotations

import logging
from uuid import UUID

from django.db import transaction

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.services.subledger_service import (
    EntitySubledgerRequest,
    create_default_entity_accounts,
)

logger = logging.getLogger(__name__)


@transaction.atomic
def create_customer_subledger(customer, *, currency_code: str = DEFAULT_CURRENCY) -> list:
    request = EntitySubledgerRequest(
        entity_type="customer",
        entity_id=str(customer.id),
        entity_name=f"{customer.first_name} {customer.last_name}",
        branch=customer.branch_id,
        currency_code=currency_code,
    )
    subledgers = create_default_entity_accounts(request=request)
    logger.info(
        "Created %d AR subledger(s) for customer %s (branch=%s)",
        len(subledgers),
        customer.id,
        customer.branch_id,
    )
    return subledgers


def get_customer_receivable_subledger(customer_id: UUID, branch: UUID | None = None):
    from apps.ledgers.models import SubLedgerAccount

    return SubLedgerAccount.objects.filter(
        entity_type="customer",
        entity_id=str(customer_id),
        ledger_purpose="Customer Receivable Ledger",
    ).first()
