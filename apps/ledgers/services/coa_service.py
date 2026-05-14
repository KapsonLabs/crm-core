from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db.models import Sum

from apps.ledgers.models import Account, LedgerEntry

DEBIT_NORMAL_TYPES = {"asset", "expense"}


def _fetch_raw_balances(
    account_ids: list,
    branch: UUID | None,
    as_of_date: date | None,
    start_date: date | None,
    end_date: date | None,
    mode: str,  # "cumulative" | "period" | "mixed"
    account_type_map: dict | None = None,
) -> dict[UUID, tuple[Decimal, Decimal]]:
    """
    Returns {account_id: (total_debit_base, total_credit_base)}.

    Modes:
        cumulative — all entries up to as_of_date (balance sheet accounts)
        period     — entries between start_date and end_date (P&L accounts)
        mixed      — cumulative for asset/liability/equity, period for income/expense
    """
    raw: dict[UUID, tuple[Decimal, Decimal]] = {}

    def _run_query(ids, qs_filter):
        rows = (
            LedgerEntry.objects
            .filter(account_id__in=ids, **qs_filter)
        )
        if branch is not None:
            rows = rows.filter(branch=branch)
        for row in rows.values("account_id").annotate(
            d=Sum("debit_base", default=Decimal("0.00")),
            c=Sum("credit_base", default=Decimal("0.00")),
        ):
            raw[row["account_id"]] = (row["d"], row["c"])

    if mode == "cumulative":
        _run_query(account_ids, {"date__lte": as_of_date})

    elif mode == "period":
        _run_query(account_ids, {"date__gte": start_date, "date__lte": end_date})

    else:  # mixed
        bs_ids = [aid for aid in account_ids if account_type_map.get(aid) in ("asset", "liability", "equity")]
        pl_ids = [aid for aid in account_ids if account_type_map.get(aid) in ("income", "expense")]
        if bs_ids and as_of_date:
            _run_query(bs_ids, {"date__lte": as_of_date})
        if pl_ids and start_date and end_date:
            _run_query(pl_ids, {"date__gte": start_date, "date__lte": end_date})

    return raw


def _signed_balance(account_type: str, debit: Decimal, credit: Decimal) -> Decimal:
    if account_type in DEBIT_NORMAL_TYPES:
        return debit - credit
    return credit - debit


def get_chart_with_balances(
    *,
    branch: UUID | None = None,
    as_of_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    account_type: str | None = None,
    include_zero_balances: bool = True,
) -> list[dict]:
    """
    Flat list of all active accounts for a branch, with aggregated balances.

    Each account's balance includes the balances of all its descendants —
    parent accounts with allows_manual_posting=False show only rolled-up values.

    Balance modes (resolved from params):
      - as_of_date only        → cumulative (all entries up to date)
      - start_date + end_date  → period-scoped
      - both sets              → mixed (cumulative for B/S, period for P&L)
      - neither                → defaults to cumulative as of today
    """
    if as_of_date is None and start_date is None:
        as_of_date = date.today()

    if as_of_date and start_date and end_date:
        mode = "mixed"
    elif start_date and end_date:
        mode = "period"
    else:
        mode = "cumulative"

    qs = Account.objects.filter(is_active=True)
    if branch is not None:
        qs = qs.filter(branch=branch)
    if account_type is not None:
        qs = qs.filter(account_type=account_type)
    accounts = list(qs)

    if not accounts:
        return []

    account_ids = [a.id for a in accounts]
    account_obj_map = {a.id: a for a in accounts}

    raw = _fetch_raw_balances(
        account_ids=account_ids,
        branch=branch,
        as_of_date=as_of_date,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        account_type_map={a.id: a.account_type for a in accounts},
    )

    # Build parent → children map; accounts whose parent is outside the filtered
    # set (inactive / different branch) are treated as roots.
    children_map: dict = defaultdict(list)
    roots: list = []
    for a in accounts:
        if a.parent_id and a.parent_id in account_obj_map:
            children_map[a.parent_id].append(a.id)
        else:
            roots.append(a.id)

    # Aggregated totals (own + all descendants)
    agg_debit: dict[UUID, Decimal] = {}
    agg_credit: dict[UUID, Decimal] = {}

    def aggregate(account_id: UUID) -> None:
        own_d, own_c = raw.get(account_id, (Decimal("0"), Decimal("0")))
        total_d, total_c = own_d, own_c
        for child_id in children_map[account_id]:
            aggregate(child_id)
            total_d += agg_debit[child_id]
            total_c += agg_credit[child_id]
        agg_debit[account_id] = total_d
        agg_credit[account_id] = total_c

    for root_id in roots:
        aggregate(root_id)

    # Compute depth (distance from nearest root ancestor)
    depth_map: dict[UUID, int] = {}

    def set_depth(account_id: UUID, depth: int) -> None:
        depth_map[account_id] = depth
        for child_id in children_map[account_id]:
            set_depth(child_id, depth + 1)

    for root_id in roots:
        set_depth(root_id, 0)

    result = []
    for account in sorted(accounts, key=lambda a: a.code):
        d = agg_debit.get(account.id, Decimal("0"))
        c = agg_credit.get(account.id, Decimal("0"))
        balance = _signed_balance(account.account_type, d, c)

        if not include_zero_balances and balance == Decimal("0"):
            continue

        result.append({
            "id": str(account.id),
            "code": account.code,
            "name": account.name,
            "account_type": account.account_type,
            "category": account.category,
            "parent_id": str(account.parent_id) if account.parent_id else None,
            "depth": depth_map.get(account.id, 0),
            "is_control_account": account.is_control_account,
            "allows_manual_posting": account.allows_manual_posting,
            "balance": str(balance),
            "debit_total": str(d),
            "credit_total": str(c),
            "children_count": len(children_map[account.id]),
        })

    return result


def get_account_drill_down(
    *,
    account_id: UUID,
    branch: UUID | None = None,
    as_of_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """
    Returns a single account node with aggregated balance + its direct children.

    Used by the drill-down endpoint — clicking a parent shows this view.
    Each child's balance is also fully aggregated (includes its own descendants).
    """
    if as_of_date is None and start_date is None:
        as_of_date = date.today()

    # Reuse the full CoA service — fast enough for typical chart sizes.
    flat = get_chart_with_balances(
        branch=branch,
        as_of_date=as_of_date,
        start_date=start_date,
        end_date=end_date,
        include_zero_balances=True,
    )
    node_map = {node["id"]: node for node in flat}

    target_id = str(account_id)
    account_node = node_map.get(target_id)
    if account_node is None:
        return {}

    children = sorted(
        [node for node in flat if node["parent_id"] == target_id],
        key=lambda n: n["code"],
    )
    return {"account": account_node, "children": children}
