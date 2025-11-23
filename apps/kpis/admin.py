from django.contrib import admin
from .models import KPI, KPIEntry, KPIAction, KPIAssignment, KPIReport


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'branch', 'source_type', 'period', 'is_active', 'created_by', 'created_at']
    list_filter = ['source_type', 'period', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'organization__name', 'branch__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = []
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'organization', 'branch')
        }),
        ('Configuration', {
            'fields': ('source_type', 'period', 'aggregate_query', 'unit')
        }),
        ('Target Values', {
            'fields': ('target_value', 'minimum_value', 'maximum_value')
        }),
        ('Status & Metadata', {
            'fields': ('is_active', 'created_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(KPIEntry)
class KPIEntryAdmin(admin.ModelAdmin):
    list_display = ['kpi', 'value', 'period_start', 'period_end', 'is_calculated', 'entered_by', 'created_at']
    list_filter = ['is_calculated', 'period_start', 'created_at']
    search_fields = ['kpi__name', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('KPI Information', {
            'fields': ('kpi',)
        }),
        ('Value & Period', {
            'fields': ('value', 'period_start', 'period_end')
        }),
        ('Metadata', {
            'fields': ('is_calculated', 'entered_by', 'notes', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(KPIAction)
class KPIActionAdmin(admin.ModelAdmin):
    list_display = ['kpi', 'action_type', 'user', 'contribution_value', 'created_at']
    list_filter = ['action_type', 'created_at']
    search_fields = ['kpi__name', 'user__username', 'user__email']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('KPI Information', {
            'fields': ('kpi',)
        }),
        ('Action Details', {
            'fields': ('action_type', 'action_data', 'contribution_value')
        }),
        ('User & Entity', {
            'fields': ('user', 'related_entity_type', 'related_entity_id')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )


@admin.register(KPIAssignment)
class KPIAssignmentAdmin(admin.ModelAdmin):
    list_display = ['kpi', 'assignment_type', 'role', 'user', 'is_active', 'assigned_by', 'created_at']
    list_filter = ['assignment_type', 'is_active', 'created_at']
    search_fields = ['kpi__name', 'role__name', 'user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('KPI Information', {
            'fields': ('kpi',)
        }),
        ('Assignment Details', {
            'fields': ('assignment_type', 'role', 'user')
        }),
        ('Status & Metadata', {
            'fields': ('is_active', 'assigned_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(KPIReport)
class KPIReportAdmin(admin.ModelAdmin):
    list_display = ['kpi', 'reported_by', 'reported_value', 'period_start', 'period_end', 'status', 'approved_by', 'created_at']
    list_filter = ['status', 'period_start', 'created_at', 'reviewed_at']
    search_fields = ['kpi__name', 'reported_by__username', 'reported_by__email', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'submitted_at', 'reviewed_at']
    
    fieldsets = (
        ('KPI Information', {
            'fields': ('kpi', 'assignment')
        }),
        ('Period & Value', {
            'fields': ('period_start', 'period_end', 'reported_value')
        }),
        ('Report Details', {
            'fields': ('notes', 'supporting_documentation')
        }),
        ('Status & Approval', {
            'fields': ('status', 'reported_by', 'approved_by', 'approval_notes')
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'reviewed_at', 'created_at', 'updated_at')
        }),
    )

