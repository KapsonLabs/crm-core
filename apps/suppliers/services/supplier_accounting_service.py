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
def create_supplier_subledger(supplier, *, currency_code: str = DEFAULT_CURRENCY) -> list:
    request = EntitySubledgerRequest(
        entity_type="supplier",
        entity_id=str(supplier.id),
        entity_name=supplier.name,
        branch=supplier.branch_id,
        currency_code=currency_code,
    )
    subledgers = create_default_entity_accounts(request=request)
    logger.info(
        "Created %d AP subledger(s) for supplier %s (branch=%s)",
        len(subledgers),
        supplier.id,
        supplier.branch_id,
    )
    return subledgers


def get_supplier_payable_subledger(supplier_id: UUID, branch: UUID | None = None):
    from apps.ledgers.models import SubLedgerAccount

    return SubLedgerAccount.objects.filter(
        entity_type="supplier",
        entity_id=str(supplier_id),
        ledger_purpose="Supplier Payable Ledger",
    ).first()
