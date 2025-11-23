"""
Management command to aggregate KPI reports and create KPI entries.

This command should be run periodically (e.g., via cron) to:
1. Aggregate approved KPI reports for each period
2. Create or update KPI entries from aggregated reports
3. Handle system-aggregated KPIs (if needed)

Usage:
    python manage.py aggregate_kpi_entries
    python manage.py aggregate_kpi_entries --period monthly
    python manage.py aggregate_kpi_entries --date 2024-01-31
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
import json

from apps.kpis.services import (
    process_all_kpis_for_period,
    process_kpi_aggregation_for_period,
    get_period_dates
)
from apps.kpis.models import KPI


class Command(BaseCommand):
    help = 'Aggregate approved KPI reports and create/update KPI entries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Reference date for aggregation (YYYY-MM-DD). Defaults to today.',
        )
        parser.add_argument(
            '--period',
            type=str,
            choices=['daily', 'weekly', 'monthly', 'quarterly', 'yearly'],
            help='Filter KPIs by period type. If not specified, processes all periods.',
        )
        parser.add_argument(
            '--kpi-id',
            type=str,
            help='Process only a specific KPI by ID.',
        )
        parser.add_argument(
            '--aggregation-method',
            type=str,
            choices=['sum', 'average', 'count'],
            default='average',
            help='Aggregation method to use. Default is "average".',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually creating/updating entries.',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting KPI aggregation...')
        
        # Parse reference date
        reference_date = timezone.now().date()
        if options.get('date'):
            try:
                reference_date = date.fromisoformat(options['date'])
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f'Invalid date format: {options["date"]}. Use YYYY-MM-DD.')
                )
                return
        
        aggregation_method = options.get('aggregation_method', 'average')
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Process specific KPI or all KPIs
        if options.get('kpi_id'):
            try:
                kpi = KPI.objects.get(id=options['kpi_id'])
                self.stdout.write(f'Processing KPI: {kpi.name} ({kpi.period})')
                
                if not dry_run:
                    entry = process_kpi_aggregation_for_period(
                        kpi, reference_date, aggregation_method
                    )
                    if entry:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Created/updated entry: {entry.value} for period {entry.period_start} to {entry.period_end}'
                            )
                        )
                    else:
                        self.stdout.write(self.style.WARNING('No approved reports found for this period'))
                else:
                    # Dry run: just show what would be processed
                    period_start, period_end = get_period_dates(kpi.period, reference_date)
                    from apps.kpis.models import KPIReport
                    reports = KPIReport.objects.filter(
                        kpi=kpi,
                        status='approved',
                        period_start=period_start,
                        period_end=period_end
                    )
                    self.stdout.write(f'Would process {reports.count()} approved report(s)')
                    
            except KPI.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'KPI with ID {options["kpi_id"]} not found.')
                )
                return
        
        else:
            # Process all KPIs
            kpi_filter = {'is_active': True, 'source_type': 'manual'}
            if options.get('period'):
                kpi_filter['period'] = options['period']
            
            kpis = KPI.objects.filter(**kpi_filter)
            
            self.stdout.write(f'Processing {kpis.count()} KPI(s) for date: {reference_date}')
            
            if not dry_run:
                results = process_all_kpis_for_period(reference_date, aggregation_method)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nAggregation completed:\n'
                        f'  - Processed: {results["processed"]} KPI(s)\n'
                        f'  - Created: {results["created"]} entry(ies)\n'
                        f'  - Updated: {results["updated"]} entry(ies)\n'
                        f'  - Skipped: {results["skipped"]} KPI(s)'
                    )
                )
                
                if results['errors']:
                    self.stdout.write(
                        self.style.ERROR(f'\nErrors encountered: {len(results["errors"])}')
                    )
                    for error in results['errors']:
                        self.stdout.write(
                            self.style.ERROR(
                                f'  - {error["kpi_name"]}: {error["error"]}'
                            )
                        )
            else:
                # Dry run: show what would be processed
                for kpi in kpis:
                    period_start, period_end = get_period_dates(kpi.period, reference_date)
                    from apps.kpis.models import KPIReport
                    reports = KPIReport.objects.filter(
                        kpi=kpi,
                        status='approved',
                        period_start=period_start,
                        period_end=period_end
                    )
                    if reports.exists():
                        self.stdout.write(
                            f'  {kpi.name}: {reports.count()} approved report(s) for period {period_start} to {period_end}'
                        )
        
        self.stdout.write(self.style.SUCCESS('\nAggregation process completed!'))

