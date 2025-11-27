from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta, date, datetime
from decimal import Decimal
import random

from apps.kpis.models import KPI, KPIEntry, KPIAction, KPIAssignment, KPIReport
from apps.organization.models import Organization, Branch
from apps.accounts.models import User, Role


class Command(BaseCommand):
    help = 'Generate sample KPI data for testing (6+ months of historical data)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--organization-id',
            type=str,
            help='Organization ID to generate KPIs for (optional)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing KPI data before generating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write('Generating sample KPI dataset...')
        
        with transaction.atomic():
            # Clear existing data if requested
            if options.get('clear'):
                self.stdout.write('Clearing existing KPI data...')
                KPIReport.objects.all().delete()
                KPIAssignment.objects.all().delete()
                KPIAction.objects.all().delete()
                KPIEntry.objects.all().delete()
                KPI.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('Cleared existing KPI data'))
            
            # Get or create organization
            organization_id = options.get('organization_id')
            if organization_id:
                try:
                    organization = Organization.objects.get(id=organization_id)
                except Organization.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'Organization with ID {organization_id} not found'))
                    return
            else:
                organization = Organization.objects.first()
                if not organization:
                    self.stdout.write(self.style.ERROR('No organization found. Please create an organization first.'))
                    return
            
            self.stdout.write(f'Using organization: {organization.name}')
            
            # Get branches
            branches = Branch.objects.filter(organization=organization, is_active=True)
            
            branch_list = list(branches)  # Include None for organization-wide KPIs
            
            # Get supervisor user or create one
            supervisor_role = Role.objects.filter(
                name='Supervisor'
            ).first()
            
            if supervisor_role:
                supervisor = supervisor_role.users.filter(is_active=True).first()
            else:
                supervisor = User.objects.filter(is_superuser=True).first()
            
            if not supervisor:
                self.stdout.write(self.style.ERROR('No supervisor user found. Please create a user with supervisor role.'))
                return
            
            self.stdout.write(f'Using supervisor: {supervisor.email}')
            
            # Get regular users for actions
            users = User.objects.filter(is_active=True).exclude(id=supervisor.id)[:10]
            if not users.exists():
                users = [supervisor]
            
            # Define sample KPIs
            kpi_definitions = [
                {
                    'name': 'Tickets Created',
                    'description': 'Total number of support tickets created',
                    'source_type': 'aggregate',
                    'period': 'daily',
                    'target_value': Decimal('50.00'),
                    'minimum_value': Decimal('30.00'),
                    'maximum_value': Decimal('100.00'),
                    'unit': 'count',
                    'aggregate_query': 'tickets.created.count()',
                },
                {
                    'name': 'Tickets Closed',
                    'description': 'Number of tickets closed per period',
                    'source_type': 'aggregate',
                    'period': 'daily',
                    'target_value': Decimal('45.00'),
                    'minimum_value': Decimal('25.00'),
                    'maximum_value': Decimal('90.00'),
                    'unit': 'count',
                    'aggregate_query': 'tickets.closed.count()',
                },
                {
                    'name': 'Average Ticket Resolution Time',
                    'description': 'Average time to resolve tickets in hours',
                    'source_type': 'aggregate',
                    'period': 'weekly',
                    'target_value': Decimal('24.00'),
                    'minimum_value': Decimal('12.00'),
                    'maximum_value': Decimal('48.00'),
                    'unit': 'hours',
                    'aggregate_query': 'tickets.avg_resolution_time()',
                },
                {
                    'name': 'Customer Satisfaction Score',
                    'description': 'Average customer satisfaction rating',
                    'source_type': 'manual',
                    'period': 'monthly',
                    'target_value': Decimal('4.50'),
                    'minimum_value': Decimal('3.50'),
                    'maximum_value': Decimal('5.00'),
                    'unit': 'rating',
                    'aggregate_query': '',
                },
                {
                    'name': 'Active Users',
                    'description': 'Number of active users on the platform',
                    'source_type': 'aggregate',
                    'period': 'weekly',
                    'target_value': Decimal('500.00'),
                    'minimum_value': Decimal('300.00'),
                    'maximum_value': Decimal('1000.00'),
                    'unit': 'count',
                    'aggregate_query': 'users.active.count()',
                },
                {
                    'name': 'Messages Sent',
                    'description': 'Total messages sent between users',
                    'source_type': 'aggregate',
                    'period': 'daily',
                    'target_value': Decimal('200.00'),
                    'minimum_value': Decimal('100.00'),
                    'maximum_value': Decimal('400.00'),
                    'unit': 'count',
                    'aggregate_query': 'messages.sent.count()',
                },
                {
                    'name': 'Number of phone calls picked up',
                    'description': 'Number of phone calls picked up by the agent',
                    'source_type': 'manual',
                    'period': 'daily',
                    'target_value': Decimal('10.00'),
                    'minimum_value': Decimal('5.00'),
                    'maximum_value': Decimal('15.00'),
                    'unit': 'count',
                    'aggregate_query': 'phone_calls.picked_up.count()',
                },
            ]
            
            # Create KPIs
            self.stdout.write('\n1. Creating KPIs...')
            created_kpis = []
            
            for kpi_def in kpi_definitions:
                for branch in branch_list:
                    kpi, created = KPI.objects.get_or_create(
                        name=kpi_def['name'],
                        organization=organization,
                        branch=branch,
                        defaults={
                            'description': kpi_def['description'],
                            'source_type': kpi_def['source_type'],
                            'period': kpi_def['period'],
                            'target_value': kpi_def['target_value'],
                            'minimum_value': kpi_def['minimum_value'],
                            'maximum_value': kpi_def['maximum_value'],
                            'unit': kpi_def['unit'],
                            'aggregate_query': kpi_def['aggregate_query'],
                            'is_active': True,
                            'created_by': supervisor,
                        }
                    )
                    created_kpis.append(kpi)
                    branch_name = branch.name if branch else 'Organization-wide'
                    status = 'Created' if created else 'Already exists'
                    self.stdout.write(f'  {status}: {kpi.name} ({branch_name})')
            
            # Generate entries for the past 6+ months
            self.stdout.write('\n2. Generating KPI entries (6+ months of data)...')
            today = timezone.now().date()
            start_date = today - timedelta(days=200)  # ~6.5 months
            
            total_entries = 0
            
            for kpi in created_kpis:
                entries_created = self._generate_entries_for_kpi(
                    kpi, start_date, today, users, supervisor
                )
                total_entries += entries_created
                self.stdout.write(f'  Created {entries_created} entries for {kpi.name}')
            
            # Generate KPI actions
            self.stdout.write('\n3. Generating KPI actions...')
            total_actions = 0
            
            for kpi in created_kpis:
                if kpi.source_type == 'aggregate':
                    actions_created = self._generate_actions_for_kpi(
                        kpi, start_date, today, users
                    )
                    total_actions += actions_created
                    self.stdout.write(f'  Created {actions_created} actions for {kpi.name}')
            
            # Create KPI assignments
            self.stdout.write('\n4. Creating KPI assignments...')
            total_assignments = 0
            all_roles = Role.objects.filter(is_active=True).filter(name='Support Agent')
            
            # Assign some KPIs to roles
            if all_roles.exists():
                for role in all_roles:  # Assign to first 3 roles
                    # Assign 2-3 KPIs per role
                    role_kpis = random.sample(created_kpis, min(4, len(created_kpis)))
                    for kpi in role_kpis:
                        assignment, created = KPIAssignment.objects.get_or_create(
                            kpi=kpi,
                            role=role,
                            defaults={
                                'assignment_type': 'role',
                                'is_active': True,
                                'assigned_by': supervisor,
                            }
                        )
                        if created:
                            total_assignments += 1
                            self.stdout.write(f'  Assigned {kpi.name} to role {role.name}')
            
            
            # Generate KPI reports for individual assignments
            self.stdout.write('\n5. Generating KPI reports...')
            total_reports = 0
            
            # Get individual user assignments
            user_assignments = KPIAssignment.objects.filter(
                assignment_type='user',
                is_active=True
            ).select_related('kpi', 'user')
            
            # Generate reports for the last 3 months
            report_start_date = today - timedelta(days=90)
            
            for assignment in user_assignments[:10]:  # Limit to first 10 assignments
                kpi = assignment.kpi
                reporting_user = assignment.user
                
                # Generate 1-3 reports per assignment
                num_reports = random.randint(1, 3)
                
                for _ in range(num_reports):
                    # Random date in the last 3 months
                    days_offset = random.randint(0, 90)
                    report_period_start = report_start_date + timedelta(days=days_offset)
                    
                    # Calculate period end based on KPI period
                    period_start, period_end = self._get_period_dates_for_kpi(
                        kpi.period, report_period_start
                    )
                    
                    # Skip if report already exists for this period
                    if KPIReport.objects.filter(
                        assignment=assignment,
                        period_start=period_start,
                        period_end=period_end
                    ).exists():
                        continue
                    
                    # Generate reported value (close to target with some variation)
                    target = float(kpi.target_value) if kpi.target_value else 50.0
                    reported_value = target * random.uniform(0.80, 1.20)
                    
                    # Ensure within bounds
                    if kpi.minimum_value:
                        reported_value = max(float(reported_value), float(kpi.minimum_value))
                    if kpi.maximum_value:
                        reported_value = min(float(reported_value), float(kpi.maximum_value))
                    
                    # Random status (draft, submitted, approved, rejected)
                    status_choices = ['draft', 'submitted', 'approved', 'rejected']
                    weights = [0.2, 0.2, 0.5, 0.1]  # More approved, fewer rejected
                    report_status = random.choices(status_choices, weights=weights)[0]
                    
                    # Create report
                    report = KPIReport.objects.create(
                        kpi=kpi,
                        assignment=assignment,
                        period_start=period_start,
                        period_end=period_end,
                        reported_value=Decimal(str(round(reported_value, 2))),
                        notes=f'Sample report for {kpi.period} period ending {period_end}',
                        status=report_status,
                        reported_by=reporting_user,
                    )
                    
                    # Set timestamps based on status
                    if report_status != 'draft':
                        report.submitted_at = timezone.now() - timedelta(days=random.randint(1, 30))
                        report.save()
                    
                    if report_status in ['approved', 'rejected']:
                        report.approved_by = supervisor
                        report.approval_notes = f'Sample approval note for {report_status} status'
                        report.reviewed_at = timezone.now() - timedelta(days=random.randint(1, 20))
                        report.save()
                        
                        # If approved, create or update KPI entry from report
                        # (only if no entry exists, to avoid conflicts with existing entries)
                        if report_status == 'approved':
                            entry, entry_created = KPIEntry.objects.get_or_create(
                                kpi=kpi,
                                period_start=period_start,
                                period_end=period_end,
                                defaults={
                                    'value': report.reported_value,
                                    'is_calculated': False,
                                    'entered_by': reporting_user,
                                    'notes': f'Approved report by {reporting_user.email}: {report.approval_notes}',
                                }
                            )
                            # If entry already existed, update notes to mention the approved report
                            if not entry_created:
                                entry.notes = f'{entry.notes} | Approved report: {report.approval_notes}'
                                entry.save()
                    
                    total_reports += 1
            
            self.stdout.write(f'  Created {total_reports} KPI reports')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully generated:\n'
                    f'  - {len(created_kpis)} KPIs\n'
                    f'  - {total_entries} KPI entries\n'
                    f'  - {total_actions} KPI actions\n'
                    f'  - {total_assignments} KPI assignments\n'
                    f'  - {total_reports} KPI reports\n'
                    f'  - Data from {start_date} to {today}'
                )
            )
    
    def _generate_entries_for_kpi(self, kpi, start_date, end_date, users, supervisor):
        """Generate entries for a KPI based on its period."""
        entries_created = 0
        current_date = start_date
        
        if kpi.period == 'daily':
            step_days = 1
            period_days = 1
        elif kpi.period == 'weekly':
            step_days = 7
            period_days = 7
        elif kpi.period == 'monthly':
            step_days = 30
            period_days = 30
        elif kpi.period == 'quarterly':
            step_days = 90
            period_days = 90
        else:  # yearly
            step_days = 365
            period_days = 365
        
        # Generate base value with trend
        base_value = float(kpi.target_value) if kpi.target_value else 50.0
        trend_factor = random.uniform(0.95, 1.05)  # Slight upward trend
        
        while current_date < end_date:
            period_start = current_date
            period_end = min(current_date + timedelta(days=period_days - 1), end_date)
            
            # Calculate value with some variation and trend
            variation = random.uniform(0.85, 1.15)
            value = base_value * variation * (trend_factor ** ((current_date - start_date).days / 30))
            
            # Add some randomness
            value += random.uniform(-5, 5)
            
            # Ensure value is within min/max if specified
            if kpi.minimum_value:
                value = max(float(value), float(kpi.minimum_value))
            if kpi.maximum_value:
                value = min(float(value), float(kpi.maximum_value))
            
            # Determine if calculated or manual
            is_calculated = kpi.source_type == 'aggregate'
            entered_by = None if is_calculated else random.choice(users) if users else supervisor
            
            # Create entry
            entry, created = KPIEntry.objects.get_or_create(
                kpi=kpi,
                period_start=period_start,
                period_end=period_end,
                defaults={
                    'value': Decimal(str(round(value, 2))),
                    'is_calculated': is_calculated,
                    'entered_by': entered_by,
                    'notes': f'Auto-generated sample data for {kpi.period} period',
                }
            )
            
            if created:
                entries_created += 1
            
            current_date += timedelta(days=step_days)
        
        return entries_created
    
    def _generate_actions_for_kpi(self, kpi, start_date, end_date, users):
        """Generate actions for aggregate KPIs."""
        actions_created = 0
        
        # Map KPI names to action types
        action_type_map = {
            'Tickets Created': 'ticket_created',
            'Tickets Closed': 'ticket_closed',
            'Messages Sent': 'message_sent',
            'Active Users': 'user_created',
        }
        
        action_type = action_type_map.get(kpi.name, 'custom')
        
        # Generate actions over the period
        current_date = start_date
        days_to_cover = (end_date - start_date).days
        
        # Generate approximately 1-5 actions per day depending on KPI
        actions_per_day = random.randint(1, 5) if 'Ticket' in kpi.name else random.randint(1, 3)
        total_actions = days_to_cover * actions_per_day
        
        # Sample dates
        action_dates = []
        for _ in range(min(total_actions, 500)):  # Limit to 500 actions per KPI
            days_offset = random.randint(0, days_to_cover)
            action_date = start_date + timedelta(days=days_offset)
            action_dates.append(action_date)
        
        action_dates.sort()
        
        for action_date in action_dates:
            user = random.choice(users) if users else None
            if not user:
                continue
            
            # Create action with timestamp
            action_datetime = timezone.make_aware(
                datetime.combine(action_date, datetime.min.time())
            ) + timedelta(hours=random.randint(9, 17))
            
            # Note: created_at is auto_now_add, so we'll use update after creation
            action = KPIAction.objects.create(
                kpi=kpi,
                action_type=action_type,
                user=user,
                contribution_value=Decimal('1.00'),
                action_data={
                    'sample': True,
                    'generated_at': action_datetime.isoformat(),
                },
            )
            # Update created_at manually since it's auto_now_add
            KPIAction.objects.filter(id=action.id).update(created_at=action_datetime)
            actions_created += 1
        
        return actions_created
    
    def _get_period_dates_for_kpi(self, period, reference_date):
        """Get start and end dates for a period based on KPI period type."""
        if period == 'daily':
            return reference_date, reference_date
        elif period == 'weekly':
            # Start of week (Monday)
            start = reference_date - timedelta(days=reference_date.weekday())
            return start, start + timedelta(days=6)
        elif period == 'monthly':
            start = reference_date.replace(day=1)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
            else:
                end = start.replace(month=start.month + 1) - timedelta(days=1)
            return start, end
        elif period == 'quarterly':
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

