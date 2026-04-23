"""
Read-only aggregation queries for analytics endpoints.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import (
    Avg,
    Count,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
)
from django.db.models.fields import DurationField
from django.db.models.functions import Coalesce, ExtractMonth
from django.utils import timezone

from apps.financials.models import Invoice, Requisition
from apps.jobs.models import Job, JobAssignment, JobProduct, Product


def resolve_organization_id(user, organization_id: str | None) -> str:
    if user.is_superuser:
        if organization_id:
            return str(organization_id)
        raise ValueError('organization_id is required for superusers.')
    if not user.organization_id:
        raise ValueError('Your account must belong to an organization.')
    if organization_id and str(organization_id) != str(user.organization_id):
        raise ValueError('organization_id does not match your organization.')
    return str(user.organization_id)


def invoice_branch_q(branch_id: str) -> Q:
    return Q(branch_id=branch_id) | Q(job__branch_id=branch_id)


def jobs_base_qs(organization_id: str, branch_id: str | None):
    qs = Job.objects.filter(organization_id=organization_id)
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    return qs


def invoices_base_qs(organization_id: str, branch_id: str | None):
    qs = Invoice.objects.filter(organization_id=organization_id).exclude(
        status=Invoice.STATUS_VOID,
    )
    if branch_id:
        qs = qs.filter(invoice_branch_q(branch_id))
    return qs


def requisitions_base_qs(organization_id: str, branch_id: str | None):
    qs = Requisition.objects.filter(
        organization_id=organization_id,
        status=Requisition.STATUS_FULFILLED,
    )
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    return qs


def requisition_attribution_expression():
    """Date/time used to bucket fulfilled requisitions (Coalesce per plan)."""
    return Coalesce(F('resolved_at'), F('updated_at'), F('created_at'))


def parse_date_param(s: str) -> date:
    return date.fromisoformat(s)


def resolve_totals_date_range(
    *,
    start_date: str | None,
    end_date: str | None,
    year: int | None,
) -> tuple[date, date]:
    if start_date and end_date:
        a = parse_date_param(start_date)
        b = parse_date_param(end_date)
        if a > b:
            raise ValueError('start_date must be on or before end_date.')
        return a, b
    if year is not None:
        return date(year, 1, 1), date(year, 12, 31)
    today = timezone.now().date()
    return date(today.year, 1, 1), date(today.year, 12, 31)


def resolve_avg_time_date_range(
    *,
    start_date: str | None,
    end_date: str | None,
    year: int | None,
) -> tuple[date, date]:
    return resolve_totals_date_range(
        start_date=start_date,
        end_date=end_date,
        year=year,
    )


def totals(
    *,
    organization_id: str,
    branch_id: str | None,
    start_date: str | None,
    end_date: str | None,
    year: int | None,
) -> dict[str, Any]:
    d0, d1 = resolve_totals_date_range(
        start_date=start_date,
        end_date=end_date,
        year=year,
    )

    jobs_qs = jobs_base_qs(organization_id, branch_id).filter(
        created_at__date__gte=d0,
        created_at__date__lte=d1,
    )
    total_jobs = jobs_qs.count()

    inv_qs = invoices_base_qs(organization_id, branch_id).filter(status__in=[Invoice.STATUS_PAID]).filter(
        issued_at__gte=d0,
        issued_at__lte=d1,
    )
    rev = inv_qs.aggregate(s=Sum('total'))['s'] or Decimal('0.00')

    req_qs = requisitions_base_qs(organization_id, branch_id)
    req_qs = req_qs.annotate(_att=requisition_attribution_expression()).filter(
        _att__date__gte=d0,
        _att__date__lte=d1,
    )
    exp = req_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    profit = rev - exp

    return {
        'total_jobs': total_jobs,
        'revenue': rev,
        'expenditure': exp,
        'profit': profit,
        'period': {'start_date': d0.isoformat(), 'end_date': d1.isoformat()},
    }


def monthly_revenue_expenditure(
    *,
    organization_id: str,
    branch_id: str | None,
    year: int,
) -> dict[str, Any]:
    d0 = date(year, 1, 1)
    d1 = date(year, 12, 31)

    inv_qs = invoices_base_qs(organization_id, branch_id).filter(
        issued_at__gte=d0,
        issued_at__lte=d1,
    )
    rev_by_month = {}
    for row in (
        inv_qs.annotate(month=ExtractMonth('issued_at'))
        .values('month')
        .annotate(s=Sum('total'))
    ):
        m = row['month']
        if m is not None:
            rev_by_month[int(m)] = row['s'] or Decimal('0.00')

    req_qs = requisitions_base_qs(organization_id, branch_id).annotate(
        _att=requisition_attribution_expression(),
    ).filter(
        _att__date__gte=d0,
        _att__date__lte=d1,
    )
    exp_by_month = {}
    for row in (
        req_qs.annotate(month=ExtractMonth('_att'))
        .values('month')
        .annotate(s=Sum('amount'))
    ):
        m = row['month']
        if m is not None:
            exp_by_month[int(m)] = row['s'] or Decimal('0.00')

    months = []
    for m in range(1, 13):
        months.append(
            {
                'month': m,
                'revenue': str(rev_by_month.get(m, Decimal('0.00'))),
                'expenditure': str(exp_by_month.get(m, Decimal('0.00'))),
            }
        )

    return {'year': year, 'months': months}


def _latest_invoice_issued_at_subquery():
    return Subquery(
        Invoice.objects.filter(job_id=OuterRef('job_id'))
        .exclude(status=Invoice.STATUS_VOID)
        .order_by('-issued_at', '-created_at')
        .values('issued_at')[:1]
    )


def top_selling(
    *,
    organization_id: str,
    branch_id: str | None,
    year: int,
) -> dict[str, Any]:
    d0 = date(year, 1, 1)
    d1 = date(year, 12, 31)

    jp = JobProduct.objects.filter(
        job__organization_id=organization_id,
    ).select_related('product')
    if branch_id:
        jp = jp.filter(job__branch_id=branch_id)

    jp = jp.annotate(
        _li_issued=_latest_invoice_issued_at_subquery(),
    ).filter(
        _li_issued__gte=d0,
        _li_issued__lte=d1,
    )

    products = (
        jp.filter(product__kind=Product.KIND_PRODUCT)
        .values('product_id', 'product__name', 'product__kind')
        .annotate(total_revenue=Sum('line_total'))
        .order_by('-total_revenue')[:5]
    )
    services = (
        jp.filter(product__kind=Product.KIND_SERVICE)
        .values('product_id', 'product__name', 'product__kind')
        .annotate(total_revenue=Sum('line_total'))
        .order_by('-total_revenue')[:5]
    )

    def _rows(rows):
        out = []
        for r in rows:
            out.append(
                {
                    'product_id': str(r['product_id']),
                    'name': r['product__name'],
                    'kind': r['product__kind'],
                    'total_revenue': str(r['total_revenue'] or Decimal('0.00')),
                }
            )
        return out

    return {
        'year': year,
        'products': _rows(products),
        'services': _rows(services),
    }


def average_time_to_service(
    *,
    organization_id: str,
    branch_id: str | None,
    start_date: str | None,
    end_date: str | None,
    year: int | None,
) -> dict[str, Any]:
    d0, d1 = resolve_avg_time_date_range(
        start_date=start_date,
        end_date=end_date,
        year=year,
    )

    qs = jobs_base_qs(organization_id, branch_id).filter(
        completed_at__isnull=False,
        completed_at__date__gte=d0,
        completed_at__date__lte=d1,
    )

    first_assigned_sq = Subquery(
        JobAssignment.objects.filter(job_id=OuterRef('pk'))
        .order_by('assigned_at')
        .values('assigned_at')[:1]
    )

    qs = qs.annotate(first_assigned=first_assigned_sq).filter(
        first_assigned__isnull=False,
    )

    qs = qs.annotate(
        delta=ExpressionWrapper(
            F('completed_at') - F('first_assigned'),
            output_field=DurationField(),
        )
    )

    agg = qs.aggregate(avg=Avg('delta'), n=Count('id'))
    n = agg['n'] or 0
    avg_delta = agg['avg']
    if n == 0 or avg_delta is None:
        return {
            'average_seconds': 0,
            'average_days': '0.00',
            'sample_size': 0,
            'period': {'start_date': d0.isoformat(), 'end_date': d1.isoformat()},
        }

    if hasattr(avg_delta, 'total_seconds'):
        total_seconds = avg_delta.total_seconds()
    else:
        total_seconds = float(avg_delta)
    avg_days = Decimal(str(total_seconds)) / Decimal('86400')

    return {
        'average_seconds': int(round(total_seconds)),
        'average_days': f'{avg_days:.2f}',
        'sample_size': n,
        'period': {'start_date': d0.isoformat(), 'end_date': d1.isoformat()},
    }
