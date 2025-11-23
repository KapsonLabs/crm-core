from rest_framework import serializers
from .models import KPI, KPIEntry, KPIAction, KPIAssignment, KPIReport
from apps.organization.serializers import OrganizationShortDetailsSerializer, BranchShortDetailsSerializer
from apps.accounts.serializers import UserDetailsSerializer, RoleShortDetailsSerializer
from apps.organization.models import Organization, Branch
from apps.accounts.models import User, Role
from apps.kpis.models import KPI


# ============================================================================
# KPI Serializers
# ============================================================================

class KPIShortDetailsSerializer(serializers.ModelSerializer):
    """Short serializer with only id and name for nested use."""
    class Meta:
        model = KPI
        fields = ['id', 'name']


class KPICreateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating KPIs."""
    organization_id = serializers.UUIDField(required=False)
    branch_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = KPI
        fields = [
            'name', 'description', 'organization_id', 'branch_id',
            'source_type', 'period', 'aggregate_query', 'unit',
            'target_value', 'minimum_value', 'maximum_value',
            'is_active'
        ]
    
    def create(self, validated_data):
        """Create KPI with organization and branch from IDs, using request.user as created_by."""
        organization_id = validated_data.pop('organization_id', None)
        if not organization_id:
            raise serializers.ValidationError({'organization_id': 'This field is required for creation.'})
        
        branch_id = validated_data.pop('branch_id', None)
        
        organization = Organization.objects.get(id=organization_id)
        validated_data['organization'] = organization
        
        if branch_id:
            branch = Branch.objects.get(id=branch_id)
            validated_data['branch'] = branch
        else:
            validated_data['branch'] = None
        
        # Use request.user from context
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update KPI with organization and branch from IDs."""
        organization_id = validated_data.pop('organization_id', None)
        branch_id = validated_data.pop('branch_id', None)
        
        if organization_id:
            organization = Organization.objects.get(id=organization_id)
            validated_data['organization'] = organization
        
        if branch_id is not None:
            if branch_id:
                branch = Branch.objects.get(id=branch_id)
                validated_data['branch'] = branch
            else:
                validated_data['branch'] = None
        
        return super().update(instance, validated_data)


class KPIDetailsSerializer(serializers.ModelSerializer):
    """Detailed serializer for KPI list and detail views."""
    organization = OrganizationShortDetailsSerializer(read_only=True)
    branch = BranchShortDetailsSerializer(read_only=True)
    created_by = UserDetailsSerializer(read_only=True)
    entries_count = serializers.SerializerMethodField()
    
    class Meta:
        model = KPI
        fields = [
            'id', 'name', 'description',
            'organization', 'branch',
            'source_type', 'period', 'aggregate_query', 'unit',
            'target_value', 'minimum_value', 'maximum_value',
            'is_active', 'created_by', 'entries_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_entries_count(self, obj):
        """Get count of entries for this KPI."""
        return obj.entries.count()


# ============================================================================
# KPI Entry Serializers
# ============================================================================

class KPIEntryShortDetailsSerializer(serializers.ModelSerializer):
    """Short serializer with only id for nested use."""
    class Meta:
        model = KPIEntry
        fields = ['id']


class KPIEntryCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating KPI entries (system/internal use only).
    
    Note: KPI entries are typically created automatically by:
    1. Aggregation service from approved KPIReports
    2. System aggregation for aggregate-type KPIs
    
    Users should not create entries directly.
    """
    kpi_id = serializers.UUIDField(required=False)
    
    class Meta:
        model = KPIEntry
        fields = [
            'kpi_id', 'value', 'period_start', 'period_end',
            'is_calculated', 'notes', 'metadata'
        ]
    
    def create(self, validated_data):
        """Create KPI Entry with KPI from ID, using request.user if manual entry."""
        kpi_id = validated_data.pop('kpi_id', None)
        if not kpi_id:
            raise serializers.ValidationError({'kpi_id': 'This field is required for creation.'})
        
        kpi = KPI.objects.get(id=kpi_id)
        validated_data['kpi'] = kpi
        
        # Set entered_by if manual entry
        is_calculated = validated_data.get('is_calculated', False)
        if not is_calculated:
            request = self.context.get('request')
            if request and request.user:
                validated_data['entered_by'] = request.user
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update KPI Entry with KPI from ID if provided."""
        kpi_id = validated_data.pop('kpi_id', None)
        
        if kpi_id:
            kpi = KPI.objects.get(id=kpi_id)
            validated_data['kpi'] = kpi
        
        return super().update(instance, validated_data)


class KPIEntryDetailsSerializer(serializers.ModelSerializer):
    """Detailed serializer for KPI entry list and detail views."""
    kpi = KPIShortDetailsSerializer(read_only=True)
    entered_by = UserDetailsSerializer(read_only=True)
    
    class Meta:
        model = KPIEntry
        fields = [
            'id', 'kpi', 'value', 'period_start', 'period_end',
            'is_calculated', 'entered_by', 'notes', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# KPI Action Serializers
# ============================================================================

class KPIActionShortDetailsSerializer(serializers.ModelSerializer):
    """Short serializer with only id for nested use."""
    class Meta:
        model = KPIAction
        fields = ['id']


class KPIActionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating KPI actions."""
    kpi_id = serializers.UUIDField(required=False)
    
    class Meta:
        model = KPIAction
        fields = [
            'kpi_id', 'action_type', 'action_data',
            'related_entity_type', 'related_entity_id',
            'contribution_value'
        ]
    
    def create(self, validated_data):
        """Create KPI Action with KPI from ID, using request.user."""
        kpi_id = validated_data.pop('kpi_id', None)
        if not kpi_id:
            raise serializers.ValidationError({'kpi_id': 'This field is required for creation.'})
        
        kpi = KPI.objects.get(id=kpi_id)
        validated_data['kpi'] = kpi
        
        # Use request.user from context
        request = self.context.get('request')
        if request and request.user:
            validated_data['user'] = request.user
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update KPI Action with KPI from ID if provided."""
        kpi_id = validated_data.pop('kpi_id', None)
        
        if kpi_id:
            kpi = KPI.objects.get(id=kpi_id)
            validated_data['kpi'] = kpi
        
        return super().update(instance, validated_data)


class KPIActionDetailsSerializer(serializers.ModelSerializer):
    """Detailed serializer for KPI action list and detail views."""
    kpi = KPIShortDetailsSerializer(read_only=True)
    user = UserDetailsSerializer(read_only=True)
    
    class Meta:
        model = KPIAction
        fields = [
            'id', 'kpi', 'action_type', 'action_data',
            'user', 'related_entity_type', 'related_entity_id',
            'contribution_value', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# ============================================================================
# KPI Assignment Serializers
# ============================================================================

class KPIAssignmentShortDetailsSerializer(serializers.ModelSerializer):
    """Short serializer with only id for nested use."""
    class Meta:
        model = KPIAssignment
        fields = ['id']


class KPIAssignmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating KPI assignments."""
    kpi_id = serializers.UUIDField(required=False)
    role_id = serializers.UUIDField(required=False, allow_null=True)
    user_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = KPIAssignment
        fields = [
            'kpi_id', 'assignment_type', 'role_id', 'user_id', 'is_active'
        ]
    
    def validate(self, data):
        """Validate that either role_id or user_id is provided based on assignment_type."""
        assignment_type = data.get('assignment_type')
        role_id = data.get('role_id')
        user_id = data.get('user_id')
        
        if assignment_type == 'role' and not role_id:
            raise serializers.ValidationError({'role_id': 'Role ID is required when assignment_type is "role".'})
        
        if assignment_type == 'user' and not user_id:
            raise serializers.ValidationError({'user_id': 'User ID is required when assignment_type is "user".'})
        
        return data
    
    def create(self, validated_data):
        """Create KPI Assignment, using request.user as assigned_by."""
        kpi_id = validated_data.pop('kpi_id', None)
        if not kpi_id:
            raise serializers.ValidationError({'kpi_id': 'This field is required for creation.'})
        role_id = validated_data.pop('role_id', None)
        user_id = validated_data.pop('user_id', None)
        
        kpi = KPI.objects.get(id=kpi_id)
        validated_data['kpi'] = kpi
        
        if role_id:
            role = Role.objects.get(id=role_id)
            validated_data['role'] = role
        
        if user_id:
            user = User.objects.get(id=user_id)
            validated_data['user'] = user
        
        # Use request.user from context
        request = self.context.get('request')
        if request and request.user:
            validated_data['assigned_by'] = request.user
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update KPI Assignment."""
        kpi_id = validated_data.pop('kpi_id', None)
        role_id = validated_data.pop('role_id', None)
        user_id = validated_data.pop('user_id', None)
        
        if kpi_id:
            kpi = KPI.objects.get(id=kpi_id)
            validated_data['kpi'] = kpi
        
        if role_id is not None:
            if role_id:
                role = Role.objects.get(id=role_id)
                validated_data['role'] = role
            else:
                validated_data['role'] = None
        
        if user_id is not None:
            if user_id:
                user = User.objects.get(id=user_id)
                validated_data['user'] = user
            else:
                validated_data['user'] = None
        
        return super().update(instance, validated_data)


class KPIAssignmentDetailsSerializer(serializers.ModelSerializer):
    """Detailed serializer for KPI assignment list and detail views."""
    kpi = KPIShortDetailsSerializer(read_only=True)
    role = RoleShortDetailsSerializer(read_only=True)
    user = UserDetailsSerializer(read_only=True)
    assigned_by = UserDetailsSerializer(read_only=True)
    
    class Meta:
        model = KPIAssignment
        fields = [
            'id', 'kpi', 'assignment_type', 'role', 'user',
            'is_active', 'assigned_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# KPI Report Serializers
# ============================================================================

class KPIReportShortDetailsSerializer(serializers.ModelSerializer):
    """Short serializer with only id for nested use."""
    class Meta:
        model = KPIReport
        fields = ['id']


class KPIReportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating KPI reports."""
    assignment_id = serializers.UUIDField(required=False)
    
    class Meta:
        model = KPIReport
        fields = [
            'assignment_id', 'period_start', 'period_end',
            'reported_value', 'notes', 'supporting_documentation'
        ]
    
    def create(self, validated_data):
        """Create KPI Report with assignment from ID, using request.user as reported_by."""
        assignment_id = validated_data.pop('assignment_id', None)
        if not assignment_id:
            raise serializers.ValidationError({'assignment_id': 'This field is required for creation.'})
        
        assignment = KPIAssignment.objects.get(id=assignment_id)
        validated_data['kpi'] = assignment.kpi
        validated_data['assignment'] = assignment
        
        # Use request.user from context
        request = self.context.get('request')
        if request and request.user:
            validated_data['reported_by'] = request.user
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update KPI Report."""
        assignment_id = validated_data.pop('assignment_id', None)
        
        if assignment_id:
            assignment = KPIAssignment.objects.get(id=assignment_id)
            validated_data['kpi'] = assignment.kpi
            validated_data['assignment'] = assignment
        
        return super().update(instance, validated_data)


class KPIReportDetailsSerializer(serializers.ModelSerializer):
    """Detailed serializer for KPI report list and detail views."""
    kpi = KPIShortDetailsSerializer(read_only=True)
    assignment = KPIAssignmentShortDetailsSerializer(read_only=True)
    reported_by = UserDetailsSerializer(read_only=True)
    approved_by = UserDetailsSerializer(read_only=True)
    
    class Meta:
        model = KPIReport
        fields = [
            'id', 'kpi', 'assignment', 'period_start', 'period_end',
            'reported_value', 'notes', 'supporting_documentation',
            'status', 'reported_by', 'approved_by', 'approval_notes',
            'submitted_at', 'reviewed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'approved_by', 'submitted_at', 'reviewed_at', 'created_at', 'updated_at']
