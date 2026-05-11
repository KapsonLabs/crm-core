from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from apps.ledgers.services.impairment_service import create_inventory_provision
from apps.ledgers.services.inventory_accrual_service import accrue_inventory_receipt
from apps.ledgers.services.inventory_posting_service import post_inventory_purchase, post_inventory_sale
from apps.ledgers.services.inventory_reconciliation_service import reconcile_physical_count
from apps.ledgers.services.landed_cost_service import allocate_landed_costs
from apps.ledgers.services.manufacturing_cost_service import complete_finished_goods, post_wip_consumption
from apps.ledgers.services.payable_service import create_supplier_invoice
from apps.ledgers.services.receivable_service import allocate_customer_payment, create_receivable_invoice
from apps.ledgers.services.rental_posting_service import post_rent_invoice
from apps.ledgers.services.sacco_posting_service import post_loan_disbursement
from apps.ledgers.services.subledger_service import EntitySubledgerRequest, create_default_entity_accounts


def example_inventory_flow(branch=None):
    inventory_item_id = uuid4()
    warehouse_id = uuid4()
    purchase = post_inventory_purchase(
        purchase_id="PO-1001",
        posting_date=date(2026, 5, 1),
        amount=Decimal("500.00"),
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        quantity_received=Decimal("10"),
        branch=branch,
        created_by_id=None,
    )
    sale_revenue, sale_cogs = post_inventory_sale(
        sale_id="SO-1001",
        posting_date=date(2026, 5, 3),
        sales_amount=Decimal("900.00"),
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        quantity_sold=Decimal("5"),
        branch=branch,
        created_by_id=None,
    )
    return {"purchase": purchase, "sale_revenue": sale_revenue, "sale_cogs": sale_cogs}


def example_landed_cost_flow(branch=None):
    return allocate_landed_costs(
        shipment_reference="SHIP-1001",
        cost_type="freight",
        allocation_method="quantity",
        amount=Decimal("250000"),
        currency_code="UGX",
        allocation_basis={"item-a": Decimal("10"), "item-b": Decimal("5")},
        allocation_date=date(2026, 5, 5),
        branch=branch,
    )


def example_manufacturing_flow(branch=None):
    return {
        "wip": post_wip_consumption(
            production_order="MO-1001",
            posting_date=date(2026, 5, 7),
            raw_material_cost=Decimal("750000"),
            branch=branch,
            created_by_id=None,
        ),
        "finished_goods": complete_finished_goods(
            production_order="MO-1001",
            posting_date=date(2026, 5, 9),
            total_cost=Decimal("900000"),
            branch=branch,
            created_by_id=None,
        ),
    }


def example_inventory_impairment_flow(branch=None):
    return create_inventory_provision(
        inventory_item_id=uuid4(),
        warehouse_id=uuid4(),
        carrying_value=Decimal("400000"),
        nrv_value=Decimal("325000"),
        assessment_date=date(2026, 5, 31),
        reason="Damaged stock write-down",
        branch=branch,
        created_by_id=None,
    )


def example_grni_flow(branch=None):
    return accrue_inventory_receipt(
        supplier_invoice_reference="GRN-1001",
        inventory_item_id=uuid4(),
        warehouse_id=uuid4(),
        accrued_amount=Decimal("600000"),
        accrual_date=date(2026, 5, 30),
        branch=branch,
        created_by_id=None,
    )


def example_inventory_reconciliation_flow(branch=None):
    return reconcile_physical_count(
        inventory_item_id=uuid4(),
        warehouse_id=uuid4(),
        physical_quantity=Decimal("18"),
        branch=branch,
    )


def example_rental_flow(branch=None):
    return post_rent_invoice(
        invoice_id="LEASE-1001",
        posting_date=date(2026, 5, 1),
        amount=Decimal("1200.00"),
        branch=branch,
        created_by_id=None,
    )


def example_sacco_flow(cash_account_id, branch=None):
    return post_loan_disbursement(
        disbursement_id="LN-1001",
        posting_date=date(2026, 5, 2),
        amount=Decimal("2500.00"),
        cash_account_id=cash_account_id,
        member_id="M-1001",
        branch=branch,
        created_by_id=None,
    )


def example_payables_flow(expense_account_id, branch=None):
    return create_supplier_invoice(
        invoice_id="BILL-1001",
        posting_date=date(2026, 5, 4),
        amount=Decimal("800.00"),
        expense_account_id=expense_account_id,
        supplier_id="SUP-1001",
        branch=branch,
        created_by_id=None,
    )


def example_multicurrency_receivable_flow(revenue_account_id, cash_account_id, branch=None):
    invoice = create_receivable_invoice(
        invoice_id="INV-USD-1001",
        posting_date=date(2026, 5, 1),
        amount=Decimal("100.00"),
        revenue_account_id=revenue_account_id,
        customer_id="CUST-1001",
        branch=branch,
        created_by_id=None,
        currency="USD",
    )
    payment = allocate_customer_payment(
        payment_id="PMT-USD-1001",
        posting_date=date(2026, 5, 15),
        amount=Decimal("100.00"),
        cash_account_id=cash_account_id,
        customer_id="CUST-1001",
        branch=branch,
        created_by_id=None,
        currency="USD",
        original_foreign_amount=Decimal("100.00"),
        original_exchange_rate=Decimal("3700.000000"),
    )
    return {"invoice": invoice, "payment": payment}


def example_customer_subledger_setup(branch=None):
    return create_default_entity_accounts(
        request=EntitySubledgerRequest(
            entity_type="customer",
            entity_id="0001",
            entity_name="ABC Ltd",
            branch=branch,
            currency_code="UGX",
        )
    )
