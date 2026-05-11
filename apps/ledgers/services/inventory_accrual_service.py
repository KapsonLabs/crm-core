from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.models import InventoryAccrual
from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal, get_configured_account


@transaction.atomic
def accrue_inventory_receipt(*, supplier_invoice_reference: str, inventory_item_id: UUID, warehouse_id: UUID, accrued_amount: Decimal, accrual_date, branch: UUID | None, created_by_id: UUID | None):
    grni_account = get_configured_account("inventory_grni", branch)
    inventory_account = get_configured_account("inventory_asset", branch)
    accrual = InventoryAccrual.objects.create(
        supplier_invoice_reference=supplier_invoice_reference,
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        accrued_amount=accrued_amount,
        accrual_date=accrual_date,
        branch=branch,
    )
    journal = create_and_post_journal(
        reference=f"GRNI-{supplier_invoice_reference}",
        journal_type="inventory_accrual",
        posting_date=accrual_date,
        description=f"GRNI accrual {supplier_invoice_reference}",
        source_module="inventory_accrual",
        source_id=supplier_invoice_reference,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-accrual:{supplier_invoice_reference}",
        lines=build_two_line_entry(
            debit_account_id=inventory_account.id,
            credit_account_id=grni_account.id,
            amount=accrued_amount,
            currency="UGX",
            description=f"GRNI accrual {supplier_invoice_reference}",
            branch=branch,
            rate_date=accrual_date,
        ),
        transaction_currency_code="UGX",
    )
    return {"accrual": accrual, "journal": journal}


@transaction.atomic
def reverse_inventory_accrual(*, inventory_accrual_id: UUID, reversal_date, branch: UUID | None, created_by_id: UUID | None):
    accrual = InventoryAccrual.objects.get(pk=inventory_accrual_id)
    grni_account = get_configured_account("inventory_grni", branch)
    inventory_account = get_configured_account("inventory_asset", branch)
    journal = create_and_post_journal(
        reference=f"GRNI-REV-{accrual.supplier_invoice_reference}",
        journal_type="inventory_accrual_reversal",
        posting_date=reversal_date,
        description=f"GRNI reversal {accrual.supplier_invoice_reference}",
        source_module="inventory_accrual",
        source_id=f"{accrual.supplier_invoice_reference}:reversal",
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-accrual-reversal:{accrual.id}",
        lines=build_two_line_entry(
            debit_account_id=grni_account.id,
            credit_account_id=inventory_account.id,
            amount=accrual.accrued_amount,
            currency="UGX",
            description=f"GRNI reversal {accrual.supplier_invoice_reference}",
            branch=branch,
            rate_date=reversal_date,
        ),
        transaction_currency_code="UGX",
    )
    accrual.status = InventoryAccrual.Status.REVERSED
    accrual.reversal_date = reversal_date
    accrual.save(update_fields=["status", "reversal_date", "updated_at"])
    return {"accrual": accrual, "journal": journal}
