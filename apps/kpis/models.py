import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal


class KPI(models.Model):
    """
    KPI Definition model - defines a KPI that can be tracked.
    Created by users with supervisor role.
    """
    
    SOURCE_TYPE_CHOICES = [
        ('aggregate', 'System Aggregate'),
        ('manual', 'Manual Entry'),
    ]
    
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="KPI name")
    description = models.TextField(blank=True, help_text="Description of what this KPI measures")
    
    # Organization and Branch relationship
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='kpis',
        help_text="Organization this KPI belongs to"
    )
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.CASCADE,
        related_name='kpis',
        null=True,
        blank=True,
        help_text="Branch this KPI is specific to (null for organization-wide)"
    )
    
    # KPI Configuration
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        help_text="How this KPI is tracked - aggregate from system or manual entry"
    )
    period = models.CharField(
        max_length=20,
        choices=PERIOD_CHOICES,
        default='monthly',
        help_text="Tracking period for this KPI"
    )
    
    # Target values
    target_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target value for this KPI"
    )
    minimum_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum acceptable value"
    )
    maximum_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum acceptable value"
    )
    
    # Unit of measurement
    unit = models.CharField(
        max_length=50,
        blank=True,
        help_text="Unit of measurement (e.g., 'count', 'percentage', 'USD', 'hours')"
    )
    
    # Aggregate configuration (if source_type is 'aggregate')
    aggregate_query = models.TextField(
        blank=True,
        help_text="Query or configuration for system aggregate KPIs"
    )
    
    # Status
    is_active = models.BooleanField(default=True, help_text="Whether this KPI is currently being tracked")
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_kpis',
        help_text="User who created this KPI (must have supervisor role)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('KPI')
        verbose_name_plural = _('KPIs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['branch', 'is_active']),
            models.Index(fields=['source_type', 'period']),
        ]
    
    def __str__(self):
        branch_info = f" - {self.branch.name}" if self.branch else ""
        return f"{self.name}{branch_info} ({self.organization.name})"
    
    def clean(self):
        """Validate KPI configuration."""
        if self.source_type == 'aggregate' and not self.aggregate_query:
            raise ValidationError({
                'aggregate_query': 'Aggregate query is required for system aggregate KPIs.'
            })
        
        if self.minimum_value is not None and self.maximum_value is not None:
            if self.minimum_value > self.maximum_value:
                raise ValidationError({
                    'minimum_value': 'Minimum value cannot be greater than maximum value.'
                })


class KPIEntry(models.Model):
    """
    KPI Entry model - actual values tracked for a KPI over time.
    
    KPIEntry can only be created through:
    1. System aggregation (is_calculated=True) - for KPIs with source_type='aggregate'
    2. Aggregation service from approved KPIReports (is_calculated=False) - for KPIs with source_type='manual'
    
    Entries are created for the reporting period of the KPI and represent
    the aggregated/final value for that period.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kpi = models.ForeignKey(
        KPI,
        on_delete=models.CASCADE,
        related_name='entries',
        help_text="KPI this entry belongs to"
    )
    
    # Value and period
    value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Actual value for this KPI entry"
    )
    period_start = models.DateField(help_text="Start date of the tracking period")
    period_end = models.DateField(help_text="End date of the tracking period")
    
    # Entry metadata
    is_calculated = models.BooleanField(
        default=False,
        help_text="Whether this value was calculated by the system or entered manually"
    )
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kpi_entries',
        help_text="User who entered this value (null if calculated)"
    )
    
    # Additional data
    notes = models.TextField(blank=True, help_text="Optional notes about this entry")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('KPI Entry')
        verbose_name_plural = _('KPI Entries')
        ordering = ['-period_start', '-created_at']
        unique_together = [['kpi', 'period_start', 'period_end']]
        indexes = [
            models.Index(fields=['kpi', 'period_start']),
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['is_calculated']),
        ]
    
    def __str__(self):
        return f"{self.kpi.name} - {self.value} ({self.period_start} to {self.period_end})"
    
    def clean(self):
        """Validate entry."""
        if self.period_start > self.period_end:
            raise ValidationError({
                'period_end': 'Period end date must be after period start date.'
            })


class KPIAction(models.Model):
    """
    KPI Action model - tracks user actions that contribute to KPIs.
    Links user actions on the platform to KPI tracking.
    """
    
    ACTION_TYPE_CHOICES = [
        ('ticket_created', 'Ticket Created'),
        ('ticket_resolved', 'Ticket Resolved'),
        ('message_sent', 'Message Sent'),
        ('user_created', 'User Created'),
        ('custom', 'Custom Action'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kpi = models.ForeignKey(
        KPI,
        on_delete=models.CASCADE,
        related_name='tracked_actions',
        help_text="KPI this action contributes to"
    )
    
    action_type = models.CharField(
        max_length=50,
        choices=ACTION_TYPE_CHOICES,
        help_text="Type of action being tracked"
    )
    action_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional data about the action"
    )
    
    # User and entity references
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='kpi_actions',
        help_text="User who performed the action"
    )
    related_entity_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of related entity (e.g., 'Ticket', 'Message')"
    )
    related_entity_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID of related entity"
    )
    
    # Value contributed
    contribution_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('1.0'),
        help_text="Value this action contributes to the KPI"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('KPI Action')
        verbose_name_plural = _('KPI Actions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['kpi', 'action_type']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['related_entity_type', 'related_entity_id']),
        ]
    
    def __str__(self):
        return f"{self.kpi.name} - {self.get_action_type_display()} by {self.user.username}"


class KPIAssignment(models.Model):
    """
    KPI Assignment model - assigns KPIs to roles or individual users.
    - If assigned to a role, all users with that role must achieve the KPI
    - If assigned to an individual user, only that user is responsible
    """
    
    ASSIGNMENT_TYPE_CHOICES = [
        ('role', 'Role Assignment'),
        ('user', 'Individual Assignment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kpi = models.ForeignKey(
        KPI,
        on_delete=models.CASCADE,
        related_name='assignments',
        help_text="KPI being assigned"
    )
    
    assignment_type = models.CharField(
        max_length=20,
        choices=ASSIGNMENT_TYPE_CHOICES,
        help_text="Type of assignment - role or individual user"
    )
    
    # Role assignment (if assignment_type is 'role')
    role = models.ForeignKey(
        'accounts.Role',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='kpi_assignments',
        help_text="Role assigned to this KPI (if assignment_type is 'role')"
    )
    
    # User assignment (if assignment_type is 'user')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='kpi_assignments',
        help_text="User assigned to this KPI (if assignment_type is 'user')"
    )
    
    # Status
    is_active = models.BooleanField(default=True, help_text="Whether this assignment is active")
    
    # Metadata
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kpi_assignments_made',
        help_text="User who made this assignment (supervisor)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('KPI Assignment')
        verbose_name_plural = _('KPI Assignments')
        ordering = ['-created_at']
        unique_together = [
            ['kpi', 'role'],  # One KPI can only be assigned to a role once
            ['kpi', 'user'],  # One KPI can only be assigned to a user once
        ]
        indexes = [
            models.Index(fields=['kpi', 'assignment_type', 'is_active']),
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        if self.assignment_type == 'role':
            return f"{self.kpi.name} → {self.role.name if self.role else 'No Role'}"
        else:
            return f"{self.kpi.name} → {self.user.email if self.user else 'No User'}"
    
    def clean(self):
        """Validate assignment."""
        if self.assignment_type == 'role' and not self.role:
            raise ValidationError({
                'role': 'Role is required when assignment_type is "role".'
            })
        
        if self.assignment_type == 'user' and not self.user:
            raise ValidationError({
                'user': 'User is required when assignment_type is "user".'
            })
        
        if self.assignment_type == 'role' and self.user:
            raise ValidationError({
                'user': 'User should not be set when assignment_type is "role".'
            })
        
        if self.assignment_type == 'user' and self.role:
            raise ValidationError({
                'role': 'Role should not be set when assignment_type is "user".'
            })


class KPIReport(models.Model):
    """
    KPI Report model - allows individual users to report on their assigned KPIs
    and get approval from supervisors.
    """
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kpi = models.ForeignKey(
        KPI,
        on_delete=models.CASCADE,
        related_name='reports',
        help_text="KPI being reported on"
    )
    assignment = models.ForeignKey(
        KPIAssignment,
        on_delete=models.CASCADE,
        related_name='reports',
        help_text="KPI assignment this report is for"
    )
    
    # Period being reported
    period_start = models.DateField(help_text="Start date of the reporting period")
    period_end = models.DateField(help_text="End date of the reporting period")
    
    # Reported value
    reported_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Value reported by the user"
    )
    
    # Report details
    notes = models.TextField(blank=True, help_text="Notes or explanation about this report")
    supporting_documentation = models.JSONField(
        default=dict,
        blank=True,
        help_text="Supporting documentation or evidence"
    )
    
    # Status and approval
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        help_text="Current status of this report"
    )
    
    # User who submitted the report
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='kpi_reports',
        help_text="User who submitted this report"
    )
    
    # Supervisor approval
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_kpi_reports',
        help_text="Supervisor who approved/rejected this report"
    )
    approval_notes = models.TextField(blank=True, help_text="Notes from supervisor on approval/rejection")
    
    # Timestamps
    submitted_at = models.DateTimeField(null=True, blank=True, help_text="When the report was submitted")
    reviewed_at = models.DateTimeField(null=True, blank=True, help_text="When the report was reviewed")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('KPI Report')
        verbose_name_plural = _('KPI Reports')
        ordering = ['-period_start', '-created_at']
        unique_together = [['assignment', 'period_start', 'period_end']]
        indexes = [
            models.Index(fields=['kpi', 'status']),
            models.Index(fields=['assignment', 'status']),
            models.Index(fields=['reported_by', 'status']),
            models.Index(fields=['period_start', 'period_end']),
        ]
    
    def __str__(self):
        return f"{self.kpi.name} Report - {self.reported_value} ({self.status}) by {self.reported_by.email}"
    
    def submit(self):
        """Submit the report for review."""
        if self.status == 'draft':
            self.status = 'submitted'
            self.submitted_at = timezone.now()
            self.save()
    
    def approve(self, supervisor, notes=''):
        """Approve the report. KPI entry will be created via aggregation service."""
        if self.status == 'submitted':
            self.status = 'approved'
            self.approved_by = supervisor
            self.approval_notes = notes
            self.reviewed_at = timezone.now()
            self.save()
            
            # Trigger aggregation for this KPI period (will be called by background task)
            # The aggregation service will create/update KPIEntry from all approved reports
    
    def reject(self, supervisor, notes=''):
        """Reject the report."""
        if self.status == 'submitted':
            self.status = 'rejected'
            self.approved_by = supervisor
            self.approval_notes = notes
            self.reviewed_at = timezone.now()
            self.save()
    
    def clean(self):
        """Validate report."""
        if self.period_start > self.period_end:
            raise ValidationError({
                'period_end': 'Period end date must be after period start date.'
            })
        
        # Reports can be created for both user and role assignments
        # For role assignments, any user with that role can report
