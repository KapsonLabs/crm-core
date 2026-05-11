from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.models import InventoryJournalEntry, InventoryJournalLine, InventoryLedgerEntry, InventoryValuationLayer
from apps.ledgers.repositories.account_repository import AccountRepository
from apps.ledgers.repositories.inventory_repository import InventoryRepository
from apps.ledgers.services.audit_service import emit_audit_log
from apps.ledgers.services.costing_service import calculate_fifo_cost as calculate_fifo_issue_cost
from apps.ledgers.services.costing_service import calculate_weighted_average_cost
from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal, get_configured_account
from apps.ledgers.utils.currency import get_exchange_rate
from apps.ledgers.utils.money import round_currency
from apps.ledgers.utils.periods import ensure_date_in_open_period


@dataclass(frozen=True)
class InventoryCostLayer:
    quantity: Decimal
    unit_cost: Decimal


def _create_inventory_journal(
    *,
    reference: str,
    journal_type: str,
    transaction_date,
    posting_date,
    source_module: str,
    source_id: str,
    currency_code: str,
    branch: UUID | None,
    description: str = "",
    extra_data: dict | None = None,
) -> InventoryJournalEntry:
    currency = AccountRepository.get_currency(currency_code)
    base_currency = AccountRepository.get_base_currency()
    exchange_rate = (
        Decimal("1.000000")
        if currency_code == base_currency.code
        else get_exchange_rate(from_currency_code=currency_code, to_currency_code=base_currency.code, rate_date=posting_date)
    )
    return InventoryJournalEntry.objects.create(
        reference=reference,
        journal_type=journal_type,
        transaction_date=transaction_date,
        posting_date=posting_date,
        source_module=source_module,
        source_id=source_id,
        currency=currency,
        exchange_rate=exchange_rate,
        branch=branch,
        description=description,
        extra_data=extra_data or {},
    )


def _post_inventory_ledger(
    *,
    journal_entry: InventoryJournalEntry,
    inventory_item_id: UUID,
    warehouse_id: UUID,
    quantity_in: Decimal,
    quantity_out: Decimal,
    value_foreign: Decimal,
    value_base: Decimal,
    valuation_layer: InventoryValuationLayer | None,
    account_id: UUID,
    description: str,
) -> InventoryLedgerEntry:
    running_quantity = (
        InventoryRepository.last_running_quantity(
            inventory_item_id=inventory_item_id,
            warehouse_id=warehouse_id,
            branch=journal_entry.branch,
        )
        + quantity_in
        - quantity_out
    )
    line = InventoryJournalLine.objects.create(
        journal_entry=journal_entry,
        account_id=account_id,
        debit=value_foreign if quantity_in > 0 else Decimal("0.00"),
        credit=value_foreign if quantity_out > 0 else Decimal("0.00"),
        debit_base=value_base if quantity_in > 0 else Decimal("0.00"),
        credit_base=value_base if quantity_out > 0 else Decimal("0.00"),
        currency=journal_entry.currency,
        exchange_rate=journal_entry.exchange_rate,
        warehouse_id=warehouse_id,
        inventory_item_id=inventory_item_id,
        quantity=quantity_in if quantity_in > 0 else quantity_out,
        description=description,
        branch=journal_entry.branch,
    )
    ledger_entry = InventoryLedgerEntry.objects.create(
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        quantity_in=quantity_in,
        quantity_out=quantity_out,
        running_quantity=running_quantity,
        inventory_value=value_foreign,
        inventory_value_base=value_base,
        valuation_layer=valuation_layer,
        journal_line=line,
        branch=journal_entry.branch,
        date=journal_entry.posting_date,
    )
    journal_entry.status = InventoryJournalEntry.Status.POSTED
    journal_entry.save(update_fields=["status", "updated_at"])
    return ledger_entry


def calculate_fifo_cost(*, quantity_to_issue: Decimal, cost_layers: list[InventoryCostLayer]) -> Decimal:
    return calculate_fifo_issue_cost(
        quantity_to_issue=quantity_to_issue,
        cost_layers=[
            {"quantity_remaining": layer.quantity, "base_unit_cost": layer.unit_cost}
            for layer in cost_layers
        ],
    )


@transaction.atomic
def post_inventory_purchase(
    *,
    purchase_id: str,
    posting_date,
    amount: Decimal,
    inventory_item_id: UUID,
    warehouse_id: UUID,
    quantity_received: Decimal,
    branch: UUID | None,
    created_by_id: UUID | None,
    currency: str = "UGX",
    payable_account_id: UUID | None = None,
    acquisition_date=None,
) -> dict:
    ensure_date_in_open_period(posting_date=posting_date, branch=branch)
    inventory_account = get_configured_account("inventory_asset", branch)
    payable_account = (
        get_configured_account("accounts_payable", branch)
        if payable_account_id is None
        else type(inventory_account).objects.get(pk=payable_account_id)
    )
    general_journal = create_and_post_journal(
        reference=f"PUR-{purchase_id}",
        journal_type="inventory_purchase",
        posting_date=posting_date,
        description=f"Inventory purchase {purchase_id}",
        source_module="inventory",
        source_id=purchase_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-purchase:{purchase_id}",
        lines=build_two_line_entry(
            debit_account_id=inventory_account.id,
            credit_account_id=payable_account.id,
            amount=amount,
            currency=currency,
            description=f"Inventory purchase {purchase_id}",
            branch=branch,
            rate_date=posting_date,
        ),
        transaction_currency_code=currency,
    )
    inventory_journal = _create_inventory_journal(
        reference=f"INVPUR-{purchase_id}",
        journal_type="inventory_receipt",
        transaction_date=acquisition_date or posting_date,
        posting_date=posting_date,
        source_module="inventory",
        source_id=purchase_id,
        currency_code=currency,
        branch=branch,
        description=f"Inventory receipt {purchase_id}",
    )
    exchange_rate = inventory_journal.exchange_rate
    base_unit_cost = round_currency((amount * exchange_rate) / quantity_received) if quantity_received > 0 else Decimal("0.00")
    valuation_layer = InventoryValuationLayer.objects.create(
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        quantity_remaining=quantity_received,
        unit_cost=round_currency(amount / quantity_received) if quantity_received > 0 else Decimal("0.00"),
        currency=inventory_journal.currency,
        exchange_rate=exchange_rate,
        base_unit_cost=base_unit_cost,
        acquisition_date=acquisition_date or posting_date,
        source_transaction=purchase_id,
        costing_method="fifo",
        branch=branch,
    )
    ledger = _post_inventory_ledger(
        journal_entry=inventory_journal,
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        quantity_in=quantity_received,
        quantity_out=Decimal("0.0000"),
        value_foreign=amount,
        value_base=round_currency(amount * exchange_rate),
        valuation_layer=valuation_layer,
        account_id=inventory_account.id,
        description=f"Inventory receipt {purchase_id}",
    )
    emit_audit_log(
        event_type="inventory.purchase.posted",
        entity_type="InventoryJournalEntry",
        entity_id=inventory_journal.id,
        branch=branch,
        performed_by_id=created_by_id,
        payload={"general_journal_id": str(general_journal.id), "valuation_layer_id": str(valuation_layer.id)},
    )
    return {"journal": general_journal, "inventory_journal": inventory_journal, "valuation_layer": valuation_layer, "ledger_entry": ledger}


@transaction.atomic
def post_inventory_sale(
    *,
    sale_id: str,
    posting_date,
    sales_amount: Decimal,
    inventory_item_id: UUID,
    warehouse_id: UUID,
    quantity_sold: Decimal,
    branch: UUID | None,
    created_by_id: UUID | None,
    currency: str = "UGX",
    receivable_account_id: UUID | None = None,
    costing_method: str = "fifo",
) -> dict:
    ensure_date_in_open_period(posting_date=posting_date, branch=branch)
    receivable_account = (
        get_configured_account("accounts_receivable", branch)
        if receivable_account_id is None
        else type(get_configured_account("accounts_receivable", branch)).objects.get(pk=receivable_account_id)
    )
    revenue_account = get_configured_account("sales_revenue", branch)
    cogs_account = get_configured_account("cogs", branch)
    inventory_account = get_configured_account("inventory_asset", branch)
    # Lock layers for the specific item/warehouse to prevent concurrent over-consumption.
    layers = list(
        InventoryRepository.valuation_layers(
            inventory_item_id=inventory_item_id,
            warehouse_id=warehouse_id,
            branch=branch,
        ).select_for_update()
    )
    if costing_method == "weighted_average":
        total_qty = sum((layer.quantity_remaining for layer in layers), Decimal("0.0000"))
        total_cost = sum((layer.quantity_remaining * layer.base_unit_cost for layer in layers), Decimal("0.00"))
        cogs_base = round_currency(calculate_weighted_average_cost(total_cost=total_cost, total_units=total_qty) * quantity_sold)
    else:
        cogs_base = calculate_fifo_issue_cost(
            quantity_to_issue=quantity_sold,
            cost_layers=[{"quantity_remaining": layer.quantity_remaining, "base_unit_cost": layer.base_unit_cost} for layer in layers],
        )
    revenue_journal = create_and_post_journal(
        reference=f"SAL-{sale_id}",
        journal_type="inventory_sale",
        posting_date=posting_date,
        description=f"Inventory sale {sale_id}",
        source_module="inventory",
        source_id=sale_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-sale-revenue:{sale_id}",
        lines=build_two_line_entry(
            debit_account_id=receivable_account.id,
            credit_account_id=revenue_account.id,
            amount=sales_amount,
            currency=currency,
            description=f"Inventory sale revenue {sale_id}",
            branch=branch,
            rate_date=posting_date,
        ),
        transaction_currency_code=currency,
    )
    cogs_journal = create_and_post_journal(
        reference=f"COGS-{sale_id}",
        journal_type="inventory_cogs",
        posting_date=posting_date,
        description=f"Cost of goods sold {sale_id}",
        source_module="inventory",
        source_id=f"{sale_id}:cogs",
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-sale-cogs:{sale_id}",
        lines=build_two_line_entry(
            debit_account_id=cogs_account.id,
            credit_account_id=inventory_account.id,
            amount=cogs_base,
            currency="UGX",
            description=f"Inventory sale cost {sale_id}",
            branch=branch,
            rate_date=posting_date,
        ),
        transaction_currency_code="UGX",
    )
    inventory_journal = _create_inventory_journal(
        reference=f"INVSALE-{sale_id}",
        journal_type="inventory_issue",
        transaction_date=posting_date,
        posting_date=posting_date,
        source_module="inventory",
        source_id=sale_id,
        currency_code="UGX",
        branch=branch,
        description=f"Inventory issue {sale_id}",
    )
    quantity_remaining = quantity_sold
    last_layer = None
    for layer in layers:
        if quantity_remaining <= 0:
            break
        consumed = min(quantity_remaining, layer.quantity_remaining)
        layer.quantity_remaining -= consumed
        layer.save(update_fields=["quantity_remaining", "updated_at"])
        quantity_remaining -= consumed
        last_layer = layer
    ledger = _post_inventory_ledger(
        journal_entry=inventory_journal,
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        quantity_in=Decimal("0.0000"),
        quantity_out=quantity_sold,
        value_foreign=cogs_base,
        value_base=cogs_base,
        valuation_layer=last_layer,
        account_id=inventory_account.id,
        description=f"Inventory issue {sale_id}",
    )
    return {"revenue_journal": revenue_journal, "cogs_journal": cogs_journal, "inventory_journal": inventory_journal, "ledger_entry": ledger}


@transaction.atomic
def post_stock_adjustment(
    *,
    adjustment_id: str,
    posting_date,
    inventory_item_id: UUID,
    warehouse_id: UUID,
    quantity: Decimal,
    amount: Decimal,
    branch: UUID | None,
    created_by_id: UUID | None,
    increase_stock: bool,
    currency: str = "UGX",
) -> dict:
    inventory_account = get_configured_account("inventory_asset", branch)
    adjustment_account = get_configured_account("inventory_adjustment", branch)
    general_journal = create_and_post_journal(
        reference=f"ADJ-{adjustment_id}",
        journal_type="stock_adjustment",
        posting_date=posting_date,
        description=f"Stock adjustment {adjustment_id}",
        source_module="inventory",
        source_id=adjustment_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"stock-adjustment:{adjustment_id}",
        lines=build_two_line_entry(
            debit_account_id=inventory_account.id if increase_stock else adjustment_account.id,
            credit_account_id=adjustment_account.id if increase_stock else inventory_account.id,
            amount=amount,
            currency=currency,
            description=f"Stock adjustment {adjustment_id}",
            branch=branch,
            rate_date=posting_date,
        ),
        transaction_currency_code=currency,
    )
    inventory_journal = _create_inventory_journal(
        reference=f"INVADJ-{adjustment_id}",
        journal_type="stock_adjustment",
        transaction_date=posting_date,
        posting_date=posting_date,
        source_module="inventory",
        source_id=adjustment_id,
        currency_code=currency,
        branch=branch,
        description=f"Inventory stock adjustment {adjustment_id}",
    )
    ledger = _post_inventory_ledger(
        journal_entry=inventory_journal,
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        quantity_in=quantity if increase_stock else Decimal("0.0000"),
        quantity_out=Decimal("0.0000") if increase_stock else quantity,
        value_foreign=amount,
        value_base=round_currency(amount * inventory_journal.exchange_rate),
        valuation_layer=None,
        account_id=inventory_account.id,
        description=f"Inventory stock adjustment {adjustment_id}",
    )
    return {"journal": general_journal, "inventory_journal": inventory_journal, "ledger_entry": ledger}


@transaction.atomic
def post_inventory_transfer(
    *,
    transfer_id: str,
    posting_date,
    inventory_item_id: UUID,
    from_warehouse_id: UUID,
    to_warehouse_id: UUID,
    quantity: Decimal,
    carrying_amount: Decimal,
    branch: UUID | None,
    created_by_id: UUID | None,
) -> dict:
    inventory_account = get_configured_account("inventory_asset", branch)
    transit_account = get_configured_account("inventory_in_transit", branch)
    transfer_out = create_and_post_journal(
        reference=f"TRF-OUT-{transfer_id}",
        journal_type="inventory_transfer_out",
        posting_date=posting_date,
        description=f"Inventory transfer out {transfer_id}",
        source_module="inventory_transfer",
        source_id=transfer_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-transfer-out:{transfer_id}",
        lines=build_two_line_entry(
            debit_account_id=transit_account.id,
            credit_account_id=inventory_account.id,
            amount=carrying_amount,
            currency="UGX",
            description=f"Inventory transfer out {transfer_id}",
            branch=branch,
            rate_date=posting_date,
        ),
        transaction_currency_code="UGX",
    )
    transfer_in = create_and_post_journal(
        reference=f"TRF-IN-{transfer_id}",
        journal_type="inventory_transfer_in",
        posting_date=posting_date,
        description=f"Inventory transfer in {transfer_id}",
        source_module="inventory_transfer",
        source_id=f"{transfer_id}:receipt",
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-transfer-in:{transfer_id}",
        lines=build_two_line_entry(
            debit_account_id=inventory_account.id,
            credit_account_id=transit_account.id,
            amount=carrying_amount,
            currency="UGX",
            description=f"Inventory transfer in {transfer_id}",
            branch=branch,
            rate_date=posting_date,
        ),
        transaction_currency_code="UGX",
    )
    return {"transfer_out_journal": transfer_out, "transfer_in_journal": transfer_in}


@transaction.atomic
def post_inventory_return(
    *,
    return_id: str,
    posting_date,
    inventory_item_id: UUID,
    warehouse_id: UUID,
    quantity: Decimal,
    amount: Decimal,
    branch: UUID | None,
    created_by_id: UUID | None,
    customer_return: bool = True,
    currency: str = "UGX",
) -> dict:
    inventory_account = get_configured_account("inventory_asset", branch)
    revenue_account = get_configured_account("sales_revenue", branch)
    receivable_account = get_configured_account("accounts_receivable", branch)
    payable_account = get_configured_account("accounts_payable", branch)
    lines = build_two_line_entry(
        debit_account_id=revenue_account.id if customer_return else inventory_account.id,
        credit_account_id=receivable_account.id if customer_return else payable_account.id,
        amount=amount,
        currency=currency,
        description=f"Inventory return {return_id}",
        branch=branch,
        rate_date=posting_date,
    )
    journal = create_and_post_journal(
        reference=f"RET-{return_id}",
        journal_type="inventory_return",
        posting_date=posting_date,
        description=f"Inventory return {return_id}",
        source_module="inventory",
        source_id=return_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-return:{return_id}",
        lines=lines,
        transaction_currency_code=currency,
    )
    return {"journal": journal}
