from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal, get_configured_account
from apps.ledgers.services.inventory_posting_service import post_inventory_transfer as post_internal_transfer


@transaction.atomic
def post_inventory_transfer(*, transfer_id: str, posting_date, inventory_item_id: UUID, from_warehouse_id: UUID, to_warehouse_id: UUID, quantity: Decimal, carrying_amount: Decimal, branch: UUID | None, created_by_id: UUID | None):
    return post_internal_transfer(
        transfer_id=transfer_id,
        posting_date=posting_date,
        inventory_item_id=inventory_item_id,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        quantity=quantity,
        carrying_amount=carrying_amount,
        branch=branch,
        created_by_id=created_by_id,
    )


def track_inventory_in_transit(*, transfer_reference: str, quantity: Decimal, amount: Decimal) -> dict:
    return {"transfer_reference": transfer_reference, "status": "in_transit", "quantity": quantity, "amount": amount}


@transaction.atomic
def receive_transferred_inventory(*, transfer_id: str, posting_date, carrying_amount: Decimal, branch: UUID | None, created_by_id: UUID | None):
    inventory_account = get_configured_account("inventory_asset", branch)
    transit_account = get_configured_account("inventory_in_transit", branch)
    return create_and_post_journal(
        reference=f"TRF-RCV-{transfer_id}",
        journal_type="inventory_transfer_receipt",
        posting_date=posting_date,
        description=f"Receipt of transferred inventory {transfer_id}",
        source_module="inventory_transfer",
        source_id=f"{transfer_id}:receive",
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-transfer-receive:{transfer_id}",
        lines=build_two_line_entry(
            debit_account_id=inventory_account.id,
            credit_account_id=transit_account.id,
            amount=carrying_amount,
            currency="UGX",
            description=f"Receipt of transferred inventory {transfer_id}",
            branch=branch,
            rate_date=posting_date,
        ),
        transaction_currency_code="UGX",
    )
