"""
KPI Aggregation Services

Services for aggregating KPI data and creating KPI entries.
Can be called from cron jobs or Redis background tasks.
"""
from django.db.models import Sum, Avg, Count, Q, F, Min, Max
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

from .models import KPI, KPIEntry, KPIReport, KPIAssignment
from apps.accounts.models import User


def get_period_dates(kpi_period, reference_date):
    """
    Get start and end dates for a KPI period based on period type.
    
    Args:
        kpi_period: One of 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
        reference_date: The date to calculate the period for
    
    Returns:
        tuple: (period_start, period_end)
    """
    if kpi_period == 'daily':
        return reference_date, reference_date
    elif kpi_period == 'weekly':
        # Start of week (Monday)
        start = reference_date - timedelta(days=reference_date.weekday())
        return start, start + timedelta(days=6)
    elif kpi_period == 'monthly':
        start = reference_date.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1) - timedelta(days=1)
        return start, end
    elif kpi_period == 'quarterly':
        quarter = (reference_date.month - 1) // 3
        start_month = quarter * 3 + 1
        start = reference_date.replace(month=start_month, day=1)
        if start_month == 10:
            end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
        else:
            end = start.replace(month=start_month + 3) - timedelta(days=1)
        return start, end
    else:  # yearly
        start = reference_date.replace(month=1, day=1)
        end = reference_date.replace(month=12, day=31)
        return start, end


def aggregate_approved_reports_for_period(kpi, period_start, period_end):
    """
    Aggregate approved KPI reports for a specific period.
    
    Args:
        kpi: KPI instance
        period_start: Start date of the period
        period_end: End date of the period
    
    Returns:
        dict: Aggregation results with 'total', 'average', 'count', 'min', 'max'
    """
    # Get all approved reports for this KPI in the period
    approved_reports = KPIReport.objects.filter(
        kpi=kpi,
        status='approved',
        period_start__lte=period_end,
        period_end__gte=period_start
    )
    
    if not approved_reports.exists():
        return None
    
    # Aggregate values
    aggregates = approved_reports.aggregate(
        total=Sum('reported_value'),
        average=Avg('reported_value'),
        count=Count('id'),
        min_value=Min('reported_value'),
        max_value=Max('reported_value')
    )
    
    return {
        'total': aggregates['total'] or Decimal('0'),
        'average': aggregates['average'] or Decimal('0'),
        'count': aggregates['count'] or 0,
        'min': aggregates['min_value'],
        'max': aggregates['max_value'],
    }


def create_kpi_entry_from_approved_reports(kpi, period_start, period_end, aggregation_method='average'):
    """
    Create or update a KPI entry from approved reports for a period.
    
    Args:
        kpi: KPI instance
        period_start: Start date of the period
        period_end: End date of the period
        aggregation_method: Method to aggregate values ('sum', 'average', 'count')
                           Default is 'average'
    
    Returns:
        KPIEntry: Created or updated KPI entry
    """
    # Get approved reports for this period
    approved_reports = KPIReport.objects.filter(
        kpi=kpi,
        status='approved',
        period_start=period_start,
        period_end=period_end
    )
    
    if not approved_reports.exists():
        return None
    
    # Aggregate based on method
    if aggregation_method == 'sum':
        aggregated_value = approved_reports.aggregate(total=Sum('reported_value'))['total']
        notes = f"Aggregated sum from {approved_reports.count()} approved report(s)"
    elif aggregation_method == 'count':
        aggregated_value = Decimal(str(approved_reports.count()))
        notes = f"Aggregated count from {approved_reports.count()} approved report(s)"
    else:  # average (default)
        aggregated_value = approved_reports.aggregate(avg=Avg('reported_value'))['avg']
        notes = f"Aggregated average from {approved_reports.count()} approved report(s)"
    
    if aggregated_value is None:
        return None
    
    # Get list of users who reported
    reporting_users = approved_reports.values_list('reported_by__email', flat=True).distinct()
    notes += f" by: {', '.join(reporting_users)}"
    
    # Create or update KPI entry
    entry, created = KPIEntry.objects.update_or_create(
        kpi=kpi,
        period_start=period_start,
        period_end=period_end,
        defaults={
            'value': aggregated_value,
            'is_calculated': False,  # Created from user reports
            'entered_by': None,  # Aggregated from multiple users
            'notes': notes,
            'metadata': {
                'source': 'aggregated_reports',
                'aggregation_method': aggregation_method,
                'reports_count': approved_reports.count(),
                'reported_by': list(reporting_users),
            }
        }
    )
    
    return entry


def process_kpi_aggregation_for_period(kpi, reference_date=None, aggregation_method='average'):
    """
    Process aggregation for a KPI for a specific period.
    
    This function:
    1. Determines the period dates based on KPI period type
    2. Aggregates approved reports for that period
    3. Creates or updates the KPI entry
    
    Args:
        kpi: KPI instance
        reference_date: Date to calculate period for (defaults to today)
        aggregation_method: Method to aggregate values ('sum', 'average', 'count')
    
    Returns:
        KPIEntry: Created or updated KPI entry, or None if no approved reports
    """
    if reference_date is None:
        reference_date = timezone.now().date()
    
    # Calculate period dates
    period_start, period_end = get_period_dates(kpi.period, reference_date)
    
    # Check if KPI source type is manual (requires user reports)
    if kpi.source_type == 'manual':
        return create_kpi_entry_from_approved_reports(
            kpi, period_start, period_end, aggregation_method
        )
    else:
        # For aggregate type KPIs, they should be calculated from system data
        # This would be handled by a separate system aggregation function
        return None


def process_all_kpis_for_period(reference_date=None, aggregation_method='average'):
    """
    Process aggregation for all active KPIs that need user reports.
    
    This is designed to be called from a cron job or background task.
    
    Args:
        reference_date: Date to calculate period for (defaults to today)
        aggregation_method: Method to aggregate values ('sum', 'average', 'count')
    
    Returns:
        dict: Summary of processed KPIs
    """
    if reference_date is None:
        reference_date = timezone.now().date()
    
    active_kpis = KPI.objects.filter(is_active=True, source_type='manual')
    
    results = {
        'processed': 0,
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': []
    }
    
    for kpi in active_kpis:
        try:
            # Calculate period dates
            period_start, period_end = get_period_dates(kpi.period, reference_date)
            
            # Check if entry already exists
            existing_entry = KPIEntry.objects.filter(
                kpi=kpi,
                period_start=period_start,
                period_end=period_end
            ).first()
            
            # Process aggregation
            entry = create_kpi_entry_from_approved_reports(
                kpi, period_start, period_end, aggregation_method
            )
            
            if entry:
                results['processed'] += 1
                if existing_entry:
                    results['updated'] += 1
                else:
                    results['created'] += 1
            else:
                results['skipped'] += 1
                
        except Exception as e:
            results['errors'].append({
                'kpi_id': str(kpi.id),
                'kpi_name': kpi.name,
                'error': str(e)
            })
            results['skipped'] += 1
    
    return results


def process_system_aggregate_kpi(kpi, period_start, period_end, aggregate_value):
    """
    Create or update a KPI entry for system-aggregated KPIs.
    
    This is for KPIs with source_type='aggregate' that are calculated
    from system data (not user reports).
    
    Args:
        kpi: KPI instance
        period_start: Start date of the period
        period_end: End date of the period
        aggregate_value: The calculated value from system data
    
    Returns:
        KPIEntry: Created or updated KPI entry
    """
    if kpi.source_type != 'aggregate':
        raise ValueError(f"KPI {kpi.name} is not an aggregate type KPI")
    
    entry, created = KPIEntry.objects.update_or_create(
        kpi=kpi,
        period_start=period_start,
        period_end=period_end,
        defaults={
            'value': Decimal(str(aggregate_value)),
            'is_calculated': True,
            'entered_by': None,
            'notes': f"System-calculated aggregate value",
            'metadata': {
                'source': 'system_aggregate',
                'aggregate_query': kpi.aggregate_query,
            }
        }
    )
    
    return entry


def get_period_label(date, period_type):
    """
    Get a human-readable label for a period.
    
    Args:
        date: Date object representing the period start
        period_type: One of 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
    
    Returns:
        str: Human-readable period label
    """
    if period_type == 'daily':
        return date.strftime('%Y-%m-%d')
    elif period_type == 'weekly':
        # Return week range (Monday to Sunday)
        week_start = date - timedelta(days=date.weekday())
        week_end = week_start + timedelta(days=6)
        return f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
    elif period_type == 'monthly':
        return date.strftime('%Y-%m')
    elif period_type == 'quarterly':
        quarter = (date.month - 1) // 3 + 1
        return f"{date.year} Q{quarter}"
    else:  # yearly
        return str(date.year)


def calculate_percentage_change(current_value, previous_value):
    """
    Calculate percentage change between two values.
    
    Args:
        current_value: Current period value
        previous_value: Previous period value (can be None)
    
    Returns:
        float or None: Percentage change, or None if previous value is None
    """
    if previous_value is None:
        return None
    
    if previous_value == 0:
        if current_value == 0:
            return 0.0
        return 100.0  # 100% increase from zero
    
    if current_value == 0 and previous_value != 0:
        return -100.0  # 100% decrease to zero
    
    return ((float(current_value) - float(previous_value)) / float(previous_value)) * 100


def calculate_trend_statistics(trend_data):
    """
    Calculate overall statistics from trend data.
    
    Args:
        trend_data: List of dictionaries with 'value' key
    
    Returns:
        dict: Statistics including averages, min, max, overall change, etc.
    """
    if not trend_data:
        return {
            'total_periods': 0,
            'current_value': None,
            'first_value': None,
            'average_value': None,
            'min_value': None,
            'max_value': None,
            'overall_change_percentage': None,
            'trend_direction': None,
        }
    
    values = [item['value'] for item in trend_data]
    current_value = values[-1]
    first_value = values[0]
    
    # Overall change from first to last
    overall_change = calculate_percentage_change(current_value, first_value)
    
    # Calculate average
    average_value = sum(values) / len(values)
    
    # Min and max
    min_value = min(values)
    max_value = max(values)
    
    # Determine trend direction
    trend_direction = None
    if overall_change is not None:
        if overall_change > 0:
            trend_direction = 'increasing'
        elif overall_change < 0:
            trend_direction = 'decreasing'
        else:
            trend_direction = 'stable'
    
    return {
        'total_periods': len(trend_data),
        'current_value': current_value,
        'first_value': first_value,
        'average_value': round(average_value, 2),
        'min_value': min_value,
        'max_value': max_value,
        'overall_change_percentage': round(overall_change, 2) if overall_change is not None else None,
        'trend_direction': trend_direction,
    }


def get_kpi_trend_analysis(kpi, periods_count=12):
    """
    Get trend analysis for a KPI with percentage changes.
    
    Args:
        kpi: KPI instance
        periods_count: Number of periods to return (0 for all)
    
    Returns:
        dict: Dictionary containing kpi info, statistics, and trends list
    """
    # Get all entries for this KPI, ordered by period
    entries = kpi.entries.all().order_by('period_start')
    
    # Build trend data with percentage changes
    trend_data = []
    previous_value = None
    
    for entry in entries:
        period_label = get_period_label(entry.period_start, kpi.period)
        
        # Calculate percentage change from previous period
        percentage_change = calculate_percentage_change(float(entry.value), previous_value)
        
        trend_data.append({
            'period_start': entry.period_start.isoformat(),
            'period_end': entry.period_end.isoformat(),
            'period_label': period_label,
            'value': float(entry.value),
            'percentage_change': round(percentage_change, 2) if percentage_change is not None else None,
            'is_increase': percentage_change > 0 if percentage_change is not None else None,
            'is_calculated': entry.is_calculated,
            'created_at': entry.created_at.isoformat(),
        })
        
        previous_value = entry.value
    
    # Limit to last N periods if specified
    if periods_count > 0:
        trend_data = trend_data[-periods_count:]
    
    # Calculate overall statistics
    statistics = calculate_trend_statistics(trend_data)
    
    return {
        'kpi': {
            'id': str(kpi.id),
            'name': kpi.name,
            'period': kpi.period,
            'unit': kpi.unit,
            'target_value': float(kpi.target_value) if kpi.target_value else None,
        },
        'statistics': statistics,
        'trends': trend_data,
    }

