"""
Celery tasks for KPI aggregation.

These tasks can be scheduled to run periodically via Redis/Celery.
"""
from celery import shared_task
from django.utils import timezone
from datetime import date
import logging
from apps.kpis.services import create_kpi_entry_from_approved_reports

from apps.kpis.services import (
    process_all_kpis_for_period,
    process_kpi_aggregation_for_period,
    process_system_aggregate_kpi
)
from apps.kpis.models import KPI

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def aggregate_kpi_reports_task(self, reference_date=None, aggregation_method='average'):
    """
    Background task to aggregate approved KPI reports and create KPI entries.
    
    This task:
    1. Processes all active KPIs with source_type='manual'
    2. Aggregates approved reports for each KPI's period
    3. Creates/updates KPI entries from aggregated reports
    
    Args:
        reference_date: Date string in YYYY-MM-DD format (defaults to today)
        aggregation_method: 'sum', 'average', or 'count' (default: 'average')
    
    Returns:
        dict: Summary of processed KPIs
    """
    try:
        if reference_date:
            if isinstance(reference_date, str):
                reference_date = date.fromisoformat(reference_date)
        else:
            reference_date = timezone.now().date()
        
        logger.info(f"Starting KPI aggregation task for date: {reference_date}")
        
        results = process_all_kpis_for_period(reference_date, aggregation_method)
        
        logger.info(
            f"Aggregation completed: {results['processed']} processed, "
            f"{results['created']} created, {results['updated']} updated, "
            f"{results['skipped']} skipped"
        )
        
        if results['errors']:
            logger.error(f"Encountered {len(results['errors'])} errors during aggregation")
            for error in results['errors']:
                logger.error(f"  - {error['kpi_name']}: {error['error']}")
        
        return results
        
    except Exception as exc:
        logger.error(f"Error in aggregate_kpi_reports_task: {str(exc)}")
        # Retry the task up to max_retries times
        raise self.retry(exc=exc, countdown=60)  # Retry after 60 seconds


@shared_task(bind=True, max_retries=3)
def aggregate_single_kpi_task(self, kpi_id, reference_date=None, aggregation_method='average'):
    """
    Background task to aggregate reports for a single KPI.
    
    Args:
        kpi_id: UUID of the KPI to process
        reference_date: Date string in YYYY-MM-DD format (defaults to today)
        aggregation_method: 'sum', 'average', or 'count' (default: 'average')
    
    Returns:
        dict: Result of the aggregation
    """
    try:
        kpi = KPI.objects.get(id=kpi_id)
        
        if reference_date:
            if isinstance(reference_date, str):
                reference_date = date.fromisoformat(reference_date)
        else:
            reference_date = timezone.now().date()
        
        logger.info(f"Processing KPI {kpi.name} for date: {reference_date}")
        
        entry = process_kpi_aggregation_for_period(kpi, reference_date, aggregation_method)
        
        if entry:
            logger.info(
                f"Created/updated entry for KPI {kpi.name}: "
                f"value={entry.value}, period={entry.period_start} to {entry.period_end}"
            )
            return {
                'success': True,
                'kpi_id': str(kpi.id),
                'kpi_name': kpi.name,
                'entry_id': str(entry.id),
                'value': float(entry.value),
                'period_start': entry.period_start.isoformat(),
                'period_end': entry.period_end.isoformat(),
            }
        else:
            logger.warning(f"No approved reports found for KPI {kpi.name}")
            return {
                'success': False,
                'kpi_id': str(kpi.id),
                'kpi_name': kpi.name,
                'message': 'No approved reports found for this period'
            }
            
    except KPI.DoesNotExist:
        logger.error(f"KPI with ID {kpi_id} not found")
        return {
            'success': False,
            'error': f'KPI with ID {kpi_id} not found'
        }
    except Exception as exc:
        logger.error(f"Error in aggregate_single_kpi_task: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def create_system_aggregate_kpi_entry_task(
    self, kpi_id, period_start, period_end, aggregate_value
):
    """
    Background task to create a KPI entry for system-aggregated KPIs.
    
    This is for KPIs with source_type='aggregate' that are calculated
    from system data (e.g., ticket counts, message counts, etc.).
    
    Args:
        kpi_id: UUID of the KPI
        period_start: Start date string in YYYY-MM-DD format
        period_end: End date string in YYYY-MM-DD format
        aggregate_value: The calculated value from system data
    
    Returns:
        dict: Result of the entry creation
    """
    try:
        kpi = KPI.objects.get(id=kpi_id)
        
        if isinstance(period_start, str):
            period_start = date.fromisoformat(period_start)
        if isinstance(period_end, str):
            period_end = date.fromisoformat(period_end)
        
        logger.info(
            f"Creating system aggregate entry for KPI {kpi.name}: "
            f"value={aggregate_value}, period={period_start} to {period_end}"
        )
        
        entry = process_system_aggregate_kpi(kpi, period_start, period_end, aggregate_value)
        
        logger.info(
            f"Created/updated system aggregate entry for KPI {kpi.name}: "
            f"entry_id={entry.id}, value={entry.value}"
        )
        
        return {
            'success': True,
            'kpi_id': str(kpi.id),
            'kpi_name': kpi.name,
            'entry_id': str(entry.id),
            'value': float(entry.value),
            'period_start': entry.period_start.isoformat(),
            'period_end': entry.period_end.isoformat(),
        }
        
    except KPI.DoesNotExist:
        logger.error(f"KPI with ID {kpi_id} not found")
        return {
            'success': False,
            'error': f'KPI with ID {kpi_id} not found'
        }
    except Exception as exc:
        logger.error(f"Error in create_system_aggregate_kpi_entry_task: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task
def trigger_kpi_aggregation_after_approval(kpi_id, period_start, period_end, aggregation_method='average'):
    """
    Trigger aggregation for a KPI after a report is approved.
    
    This task is called immediately after a report is approved to ensure
    the KPI entry is updated with the latest aggregated value.
    
    Args:
        kpi_id: UUID of the KPI
        period_start: Start date string in YYYY-MM-DD format
        period_end: End date string in YYYY-MM-DD format
        aggregation_method: 'sum', 'average', or 'count' (default: 'average')
    
    Returns:
        dict: Result of the aggregation
    """
    try:
        
        kpi = KPI.objects.get(id=kpi_id)
        
        if isinstance(period_start, str):
            period_start = date.fromisoformat(period_start)
        if isinstance(period_end, str):
            period_end = date.fromisoformat(period_end)
        
        logger.info(
            f"Triggering aggregation after approval for KPI {kpi.name}, "
            f"period {period_start} to {period_end}"
        )
        
        entry = create_kpi_entry_from_approved_reports(
            kpi, period_start, period_end, aggregation_method
        )
        
        if entry:
            logger.info(f"Updated KPI entry after approval: entry_id={entry.id}, value={entry.value}")
            return {
                'success': True,
                'entry_id': str(entry.id),
                'value': float(entry.value)
            }
        else:
            logger.warning(f"No approved reports found for aggregation")
            return {
                'success': False,
                'message': 'No approved reports found'
            }
            
    except Exception as exc:
        logger.error(f"Error in trigger_kpi_aggregation_after_approval: {str(exc)}")
        return {
            'success': False,
            'error': str(exc)
        }

