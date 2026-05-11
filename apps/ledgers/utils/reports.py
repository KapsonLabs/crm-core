from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from apps.ledgers.constants import AccountTypes, DEFAULT_CURRENCY
from apps.ledgers.repositories.reporting_repository import ReportingRepository


def _balance_for(item: dict) -> Decimal:
    if item["account__account_type"] in (AccountTypes.ASSET, AccountTypes.EXPENSE):
        return item["debit_total"] - item["credit_total"]
    return item["credit_total"] - item["debit_total"]


def _cumulative_balances(as_of_date: date, branch: UUID | None = None) -> dict[str, list[dict]]:
    """Balance-sheet bucket: cumulative from inception to as_of_date."""
    buckets: dict[str, list[dict]] = {
        AccountTypes.ASSET: [],
        AccountTypes.LIABILITY: [],
        AccountTypes.EQUITY: [],
        AccountTypes.INCOME: [],
        AccountTypes.EXPENSE: [],
    }
    for item in ReportingRepository.account_totals(as_of_date=as_of_date, branch=branch):
        item["balance"] = _balance_for(item)
        buckets[item["account__account_type"]].append(item)
    return buckets


def _period_balances(start_date: date, end_date: date, branch: UUID | None = None) -> dict[str, list[dict]]:
    """Period bucket: only entries between start_date and end_date (inclusive)."""
    buckets: dict[str, list[dict]] = {
        AccountTypes.ASSET: [],
        AccountTypes.LIABILITY: [],
        AccountTypes.EQUITY: [],
        AccountTypes.INCOME: [],
        AccountTypes.EXPENSE: [],
    }
    for item in ReportingRepository.account_totals_for_period(
        start_date=start_date,
        end_date=end_date,
        branch=branch,
    ):
        item["balance"] = _balance_for(item)
        buckets[item["account__account_type"]].append(item)
    return buckets


def generate_balance_sheet(as_of_date: date, branch: UUID | None = None) -> dict:
    balances = _cumulative_balances(as_of_date=as_of_date, branch=branch)
    total_assets = sum((i["balance"] for i in balances[AccountTypes.ASSET]), Decimal("0.00"))
    total_liabilities = sum((i["balance"] for i in balances[AccountTypes.LIABILITY]), Decimal("0.00"))
    total_equity = sum((i["balance"] for i in balances[AccountTypes.EQUITY]), Decimal("0.00"))
    return {
        "assets": balances[AccountTypes.ASSET],
        "liabilities": balances[AccountTypes.LIABILITY],
        "equity": balances[AccountTypes.EQUITY],
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "balance_check": total_assets - (total_liabilities + total_equity),
        "as_of_date": as_of_date,
        "report_currency": DEFAULT_CURRENCY,
    }


def generate_income_statement(start_date: date, end_date: date, branch: UUID | None = None) -> dict:
    balances = _period_balances(start_date=start_date, end_date=end_date, branch=branch)
    total_income = sum((i["balance"] for i in balances[AccountTypes.INCOME]), Decimal("0.00"))
    total_expenses = sum((i["balance"] for i in balances[AccountTypes.EXPENSE]), Decimal("0.00"))
    return {
        "income": balances[AccountTypes.INCOME],
        "expenses": balances[AccountTypes.EXPENSE],
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses,
        "start_date": start_date,
        "end_date": end_date,
        "report_currency": DEFAULT_CURRENCY,
    }


def generate_profit_loss(start_date: date, end_date: date, branch: UUID | None = None) -> dict:
    return generate_income_statement(start_date=start_date, end_date=end_date, branch=branch)


def generate_cashflow_statement(start_date: date, end_date: date, branch: UUID | None = None) -> dict:
    """Indirect-method approximation using period income/expense movements.

    A full IAS 7 direct-method statement requires tagging each cash movement by
    activity (operating / investing / financing), which requires source-transaction
    metadata beyond what the GL alone provides.  This simplified version is useful
    for period-level management reporting and reconciles to net profit.
    """
    period = _period_balances(start_date=start_date, end_date=end_date, branch=branch)
    cumulative = _cumulative_balances(as_of_date=end_date, branch=branch)

    operating_inflows = sum((i["balance"] for i in period[AccountTypes.INCOME]), Decimal("0.00"))
    operating_outflows = sum((i["balance"] for i in period[AccountTypes.EXPENSE]), Decimal("0.00"))
    net_operating = operating_inflows - operating_outflows

    # Net change in working capital items (assets & liabilities) for the period
    # approximated as the change in cumulative balances. A proper IAS 7 implementation
    # requires explicit tagging by activity which belongs in the operational layer.
    total_assets = sum((i["balance"] for i in cumulative[AccountTypes.ASSET]), Decimal("0.00"))
    total_liabilities = sum((i["balance"] for i in cumulative[AccountTypes.LIABILITY]), Decimal("0.00"))

    return {
        "operating_inflows": operating_inflows,
        "operating_outflows": operating_outflows,
        "net_operating_cashflow": net_operating,
        "total_assets_as_of_end": total_assets,
        "total_liabilities_as_of_end": total_liabilities,
        "start_date": start_date,
        "end_date": end_date,
        "report_currency": DEFAULT_CURRENCY,
    }
