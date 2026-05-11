from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.models import LandedCostAllocation
from apps.ledgers.repositories.account_repository import AccountRepository
from apps.ledgers.utils.currency import get_exchange_rate
from apps.ledgers.utils.money import round_currency


def distribute_freight_costs(*, total_amount: Decimal, basis_values: dict[str, Decimal]) -> dict[str, Decimal]:
    total_basis = sum(basis_values.values(), Decimal("0.00"))
    if total_basis <= 0:
        return {key: Decimal("0.00") for key in basis_values}
    return {key: round_currency(total_amount * value / total_basis) for key, value in basis_values.items()}


def capitalize_import_costs(*, purchase_cost: Decimal, import_duty: Decimal, freight: Decimal, insurance: Decimal) -> Decimal:
    return round_currency(purchase_cost + import_duty + freight + insurance)


@transaction.atomic
def allocate_landed_costs(
    *,
    shipment_reference: str,
    cost_type: str,
    allocation_method: str,
    amount: Decimal,
    currency_code: str,
    allocation_basis: dict[str, Decimal],
    allocation_date,
    branch: UUID | None = None,
) -> list[LandedCostAllocation]:
    base_currency = AccountRepository.get_base_currency()
    currency = AccountRepository.get_currency(currency_code)
    exchange_rate = get_exchange_rate(
        from_currency_code=currency_code,
        to_currency_code=base_currency.code,
        rate_date=allocation_date,
    )
    distributed = distribute_freight_costs(total_amount=amount, basis_values=allocation_basis)
    rows = []
    for key, allocated_amount in distributed.items():
        rows.append(
            LandedCostAllocation.objects.create(
                shipment_reference=shipment_reference,
                cost_type=cost_type,
                allocation_method=allocation_method,
                amount=allocated_amount,
                currency=currency,
                exchange_rate=exchange_rate,
                allocated_at=datetime.combine(allocation_date, datetime.min.time()),
                branch=branch,
                allocation_basis={"target": key, "basis_value": str(allocation_basis[key])},
            )
        )
    return rows
