from __future__ import annotations

import logging

from django.db import transaction

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.services.subledger_service import (
    EntitySubledgerRequest,
    create_default_entity_accounts,
)

logger = logging.getLogger(__name__)


@transaction.atomic
def create_product_subledger(product, *, currency_code: str = DEFAULT_CURRENCY) -> list:
    """
    Create inventory subledgers (asset, COGS, adjustment, variance) for a physical
    product. Must only be called when product.kind == 'product'; services have no
    inventory and do not require subledgers.
    """
    request = EntitySubledgerRequest(
        entity_type="product",
        entity_id=str(product.id),
        entity_name=product.name,
        branch=product.branch_id,
        currency_code=currency_code,
    )
    subledgers = create_default_entity_accounts(request=request)
    logger.info(
        "Created %d inventory subledger(s) for product %s (branch=%s)",
        len(subledgers),
        product.id,
        product.branch_id,
    )
    return subledgers
