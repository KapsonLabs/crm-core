from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Avg
from django.utils import timezone
from datetime import timedelta
import logging

from .models import KPI, KPIEntry, KPIAction, KPIAssignment, KPIReport
from .services import (
    process_kpi_aggregation_for_period,
    get_period_dates,
    create_kpi_entry_from_approved_reports,
    get_kpi_trend_analysis
)
from apps.kpis.tasks import trigger_kpi_aggregation_after_approval

from .serializers import (
    KPICreateSerializer, KPIDetailsSerializer,
    KPIEntryCreateSerializer, KPIEntryDetailsSerializer,
    KPIActionCreateSerializer, KPIActionDetailsSerializer,
    KPIAssignmentCreateSerializer, KPIAssignmentDetailsSerializer,
    KPIReportCreateSerializer, KPIReportDetailsSerializer,
)
from apps.accounts.models import Role, User


class KPIListCreateView(APIView):
    """List and create KPIs. Only supervisors can create."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get list of KPIs filtered by query params."""
        queryset = KPI.objects.select_related('organization', 'branch', 'created_by').all()
        
        organization_id = request.query_params.get('organization_id')
        if organization_id:
            queryset = queryset.filter(organization__id=organization_id)
        
        branch_id = request.query_params.get('branch_id')
        if branch_id:
            queryset = queryset.filter(branch__id=branch_id)
        
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        queryset = queryset.order_by('-created_at')
        serializer = KPIDetailsSerializer(queryset, many=True)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create KPI - only supervisors can create."""
        # Check if user has supervisor role
        user = request.user
        supervisor_role = Role.objects.filter(
            Q(name='Supervisor') | Q(slug__in=['supervisor', 'manager']),
            users=user,
            is_active=True
        ).first()
        
        if not supervisor_role and not user.is_superuser:
            return Response(
                {'status': 403, 'message': 'Only users with supervisor role can create KPIs.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = KPICreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            {"status": 201, "data": KPIDetailsSerializer(instance).data},
            status=status.HTTP_201_CREATED
        )


class KPIDetailView(APIView):
    """Retrieve, update, or delete a KPI."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get KPI details."""
        kpi = get_object_or_404(KPI.objects.select_related('organization', 'branch', 'created_by'), id=pk)
        serializer = KPIDetailsSerializer(kpi)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)
    
    def put(self, request, pk):
        """Update KPI."""
        kpi = get_object_or_404(KPI.objects.select_related('organization', 'branch', 'created_by'), id=pk)
        serializer = KPICreateSerializer(kpi, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({"status": 200, "data": KPIDetailsSerializer(instance).data}, status=status.HTTP_200_OK)
    
    def patch(self, request, pk):
        """Partially update KPI."""
        kpi = get_object_or_404(KPI.objects.select_related('organization', 'branch', 'created_by'), id=pk)
        serializer = KPICreateSerializer(kpi, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({"status": 200, "data": KPIDetailsSerializer(instance).data}, status=status.HTTP_200_OK)
    
    def delete(self, request, pk):
        """Delete KPI - only supervisors can delete."""
        kpi = get_object_or_404(KPI, id=pk)
        
        user = request.user
        supervisor_role = Role.objects.filter(
            Q(name='Supervisor') | Q(slug__in=['supervisor', 'manager']),
            users=user,
            is_active=True
        ).first()
        
        if not supervisor_role and not user.is_superuser:
            return Response(
                {'status': 403, 'message': 'Only users with supervisor role can delete KPIs.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        kpi.delete()
        return Response({"status": 204}, status=status.HTTP_204_NO_CONTENT)


class KPIEntryListView(APIView):
    """List KPI entries. Entries are created automatically by aggregation service."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get list of KPI entries filtered by query params."""
        queryset = KPIEntry.objects.select_related('kpi', 'kpi__organization', 'kpi__branch', 'entered_by').all()
        
        organization_id = request.query_params.get('organization_id')
        if organization_id:
            queryset = queryset.filter(kpi__organization__id=organization_id)
        
        kpi_id = request.query_params.get('kpi_id')
        if kpi_id:
            queryset = queryset.filter(kpi__id=kpi_id)
        
        branch_id = request.query_params.get('branch_id')
        if branch_id:
            queryset = queryset.filter(kpi__branch__id=branch_id)
        
        queryset = queryset.order_by('-period_start', '-created_at')
        serializer = KPIEntryDetailsSerializer(queryset, many=True)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)


class KPIEntryDetailView(APIView):
    """Retrieve a KPI entry. Entries are read-only and created by aggregation service."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get KPI entry details."""
        entry = get_object_or_404(KPIEntry.objects.select_related('kpi', 'entered_by'), id=pk)
        serializer = KPIEntryDetailsSerializer(entry)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)


class KPIActionListCreateView(APIView):
    """List and create KPI actions."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get list of KPI actions filtered by query params."""
        queryset = KPIAction.objects.select_related('kpi', 'kpi__organization', 'user').all()
        
        organization_id = request.query_params.get('organization_id')
        if organization_id:
            queryset = queryset.filter(kpi__organization__id=organization_id)
        
        kpi_id = request.query_params.get('kpi_id')
        if kpi_id:
            queryset = queryset.filter(kpi__id=kpi_id)
        
        user_id = request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user__id=user_id)
        
        action_type = request.query_params.get('action_type')
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        queryset = queryset.order_by('-created_at')
        serializer = KPIActionDetailsSerializer(queryset, many=True)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create KPI action. Set user to current user if not provided."""
        serializer = KPIActionCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            {"status": 201, "data": KPIActionDetailsSerializer(instance).data},
            status=status.HTTP_201_CREATED
        )


class KPIActionDetailView(APIView):
    """Retrieve, update, or delete a KPI action."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get KPI action details."""
        action = get_object_or_404(KPIAction.objects.select_related('kpi', 'user'), id=pk)
        serializer = KPIActionDetailsSerializer(action)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)
    
    def put(self, request, pk):
        """Update KPI action."""
        action = get_object_or_404(KPIAction.objects.select_related('kpi', 'user'), id=pk)
        serializer = KPIActionCreateSerializer(action, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({"status": 200, "data": KPIActionDetailsSerializer(instance).data}, status=status.HTTP_200_OK)
    
    def patch(self, request, pk):
        """Partially update KPI action."""
        action = get_object_or_404(KPIAction.objects.select_related('kpi', 'user'), id=pk)
        serializer = KPIActionCreateSerializer(action, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({"status": 200, "data": KPIActionDetailsSerializer(instance).data}, status=status.HTTP_200_OK)
    
    def delete(self, request, pk):
        """Delete KPI action."""
        action = get_object_or_404(KPIAction, id=pk)
        action.delete()
        return Response({"status": 204}, status=status.HTTP_204_NO_CONTENT)


class KPIStatsView(APIView):
    """Get statistics for a KPI."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, kpi_id):
        """Get KPI statistics including current value, target comparison, etc."""
        kpi = get_object_or_404(KPI, id=kpi_id)
        
        # Get latest entry
        latest_entry = kpi.entries.order_by('-period_start').first()
        
        # Get all entries count
        entries_count = kpi.entries.count()
        
        # Calculate average value
        avg_value = kpi.entries.aggregate(avg=Avg('value'))['avg']
        
        stats = {
            'kpi_id': str(kpi.id),
            'kpi_name': kpi.name,
            'target_value': float(kpi.target_value) if kpi.target_value else None,
            'latest_value': float(latest_entry.value) if latest_entry else None,
            'latest_period_start': latest_entry.period_start.isoformat() if latest_entry else None,
            'latest_period_end': latest_entry.period_end.isoformat() if latest_entry else None,
            'entries_count': entries_count,
            'average_value': float(avg_value) if avg_value else None,
            'actions_count': kpi.tracked_actions.count(),
        }
        
        # Calculate target achievement if target exists
        if kpi.target_value and latest_entry:
            achievement_percentage = (float(latest_entry.value) / float(kpi.target_value)) * 100
            stats['target_achievement_percentage'] = round(achievement_percentage, 2)
        
        return Response({"status": 200, "data": stats}, status=status.HTTP_200_OK)


class KPITrendAnalysisView(APIView):
    """Get trend analysis for a KPI showing values over time and percentage changes."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, kpi_id):
        """
        Get trend analysis for a KPI.
        
        Returns aggregated values per period (month, week, etc.) based on KPI period type,
        along with percentage change from previous period.
        
        Query params:
            - periods: Number of periods to return (default: 12)
        """
        kpi = get_object_or_404(KPI, id=kpi_id)
        
        # Get number of periods to analyze (default to 12)
        periods_count = int(request.query_params.get('periods', 12))
        
        # Get trend analysis using service function
        trend_analysis = get_kpi_trend_analysis(kpi, periods_count)
        
        return Response({
            "status": 200,
            "data": trend_analysis
        }, status=status.HTTP_200_OK)


class UserKPIsView(APIView):
    """View for logged-in users to see their assigned KPIs and performance."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all KPIs assigned to the current user (via role or direct assignment)."""
        user = request.user
        
        # Get KPIs assigned directly to the user
        user_assignments = KPIAssignment.objects.filter(
            user=user,
            is_active=True,
            assignment_type='user'
        ).select_related('kpi', 'kpi__organization', 'kpi__branch')
        
        # Get KPIs assigned to user's role (if user has a role)
        role_assignments = KPIAssignment.objects.none()
        if user.role:
            role_assignments = KPIAssignment.objects.filter(
                role=user.role,
                is_active=True,
                assignment_type='role'
            ).select_related('kpi', 'kpi__organization', 'kpi__branch')
        
        # Combine and get unique KPIs
        all_assignments = list(user_assignments) + list(role_assignments)
        kpi_ids = set(assignment.kpi_id for assignment in all_assignments)
        kpis = KPI.objects.filter(id__in=kpi_ids, is_active=True)
        
        # Build performance data for each KPI
        performance_data = []
        
        for kpi in kpis:
            # Get latest entry
            latest_entry = kpi.entries.order_by('-period_start').first()
            
            # Get entries for current period
            today = timezone.now().date()
            current_period_start, current_period_end = self._get_period_dates(kpi.period, today)
            current_period_entry = kpi.entries.filter(
                period_start=current_period_start,
                period_end=current_period_end
            ).first()
            
            # Calculate performance metrics
            avg_value = kpi.entries.aggregate(avg=Avg('value'))['avg']
            total_entries = kpi.entries.count()
            
            # Get assignment info
            assignment = next(
                (a for a in all_assignments if a.kpi_id == kpi.id),
                None
            )
            
            # Calculate achievement percentage
            achievement_percentage = None
            if kpi.target_value and latest_entry:
                achievement_percentage = round(
                    (float(latest_entry.value) / float(kpi.target_value)) * 100, 2
                )
            
            # Get pending reports count (for individual assignments)
            pending_reports_count = 0
            if assignment and assignment.assignment_type == 'user':
                pending_reports_count = kpi.reports.filter(
                    assignment=assignment,
                    status__in=['draft', 'submitted']
                ).count()
            
            performance_data.append({
                'kpi': KPIDetailsSerializer(kpi).data,
                'assignment': KPIAssignmentDetailsSerializer(assignment).data if assignment else None,
                'latest_value': float(latest_entry.value) if latest_entry else None,
                'latest_period_start': latest_entry.period_start.isoformat() if latest_entry else None,
                'latest_period_end': latest_entry.period_end.isoformat() if latest_entry else None,
                'current_period_value': float(current_period_entry.value) if current_period_entry else None,
                'current_period_start': current_period_start.isoformat(),
                'current_period_end': current_period_end.isoformat(),
                'target_value': float(kpi.target_value) if kpi.target_value else None,
                'average_value': float(avg_value) if avg_value else None,
                'total_entries': total_entries,
                'achievement_percentage': achievement_percentage,
                'is_on_track': (
                    achievement_percentage >= 90 if achievement_percentage is not None else None
                ),
                'pending_reports_count': pending_reports_count,
            })
        
        # Calculate average performance (average of all achievement_percentage values)
        achievement_percentages = [
            item['achievement_percentage'] 
            for item in performance_data 
            if item['achievement_percentage'] is not None
        ]
        average_performance = None
        if achievement_percentages:
            average_performance = round(sum(achievement_percentages) / len(achievement_percentages), 2)
        
        return Response({
            "status": 200,
            "data": {
                "kpis": performance_data,
                "total_kpis": len(performance_data),
                "average_performance": average_performance
            }
        }, status=status.HTTP_200_OK)
    
    def _get_period_dates(self, period, reference_date):
        """Get start and end dates for the current period."""
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


class KPIAssignmentListCreateView(APIView):
    """List and create KPI assignments."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get list of KPI assignments filtered by query params."""
        queryset = KPIAssignment.objects.select_related(
            'kpi', 'kpi__organization', 'role', 'user', 'assigned_by'
        ).all()
        
        kpi_id = request.query_params.get('kpi_id')
        if kpi_id:
            queryset = queryset.filter(kpi__id=kpi_id)
        
        role_id = request.query_params.get('role_id')
        if role_id:
            queryset = queryset.filter(role__id=role_id)
        
        user_id = request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user__id=user_id)
        
        assignment_type = request.query_params.get('assignment_type')
        if assignment_type:
            queryset = queryset.filter(assignment_type=assignment_type)
        
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        queryset = queryset.order_by('-created_at')
        serializer = KPIAssignmentDetailsSerializer(queryset, many=True)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create KPI assignment - only supervisors can create."""
        user = request.user
        supervisor_role = Role.objects.filter(
            Q(name='Supervisor') | Q(slug__in=['supervisor', 'manager']),
            users=user,
            is_active=True
        ).first()
        
        if not supervisor_role and not user.is_superuser:
            return Response(
                {'status': 403, 'message': 'Only users with supervisor role can create KPI assignments.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = KPIAssignmentCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            {"status": 201, "data": KPIAssignmentDetailsSerializer(instance).data},
            status=status.HTTP_201_CREATED
        )


class KPIAssignmentDetailView(APIView):
    """Retrieve, update, or delete a KPI assignment."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get KPI assignment details."""
        assignment = get_object_or_404(
            KPIAssignment.objects.select_related('kpi', 'role', 'user', 'assigned_by'),
            id=pk
        )
        serializer = KPIAssignmentDetailsSerializer(assignment)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)
    
    def put(self, request, pk):
        """Update KPI assignment."""
        assignment = get_object_or_404(KPIAssignment, id=pk)
        serializer = KPIAssignmentCreateSerializer(assignment, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({"status": 200, "data": KPIAssignmentDetailsSerializer(instance).data}, status=status.HTTP_200_OK)
    
    def patch(self, request, pk):
        """Partially update KPI assignment."""
        assignment = get_object_or_404(KPIAssignment, id=pk)
        serializer = KPIAssignmentCreateSerializer(assignment, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({"status": 200, "data": KPIAssignmentDetailsSerializer(instance).data}, status=status.HTTP_200_OK)
    
    def delete(self, request, pk):
        """Delete KPI assignment - only supervisors can delete."""
        assignment = get_object_or_404(KPIAssignment, id=pk)
        
        user = request.user
        supervisor_role = Role.objects.filter(
            Q(name='Supervisor') | Q(slug__in=['supervisor', 'manager']),
            users=user,
            is_active=True
        ).first()
        
        if not supervisor_role and not user.is_superuser:
            return Response(
                {'status': 403, 'message': 'Only users with supervisor role can delete KPI assignments.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        assignment.delete()
        return Response({"status": 204}, status=status.HTTP_204_NO_CONTENT)


class KPIReportListCreateView(APIView):
    """List and create KPI reports."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get list of KPI reports filtered by query params."""
        queryset = KPIReport.objects.select_related(
            'kpi', 'assignment', 'reported_by', 'approved_by'
        ).all()
        
        # Regular users can only see their own reports
        user = request.user
        supervisor_role = Role.objects.filter(
            Q(name='Supervisor') | Q(slug__in=['supervisor', 'manager']),
            users=user,
            is_active=True
        ).first()
        
        if not supervisor_role and not user.is_superuser:
            queryset = queryset.filter(reported_by=user)
        
        kpi_id = request.query_params.get('kpi_id')
        if kpi_id:
            queryset = queryset.filter(kpi__id=kpi_id)
        
        assignment_id = request.query_params.get('assignment_id')
        if assignment_id:
            queryset = queryset.filter(assignment__id=assignment_id)
        
        user_id = request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(reported_by__id=user_id)
        
        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        queryset = queryset.order_by('-period_start', '-created_at')
        serializer = KPIReportDetailsSerializer(queryset, many=True)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create KPI report - users can only create for their own assignments."""
        serializer = KPIReportCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # Verify user is assigned to this KPI
        assignment_id = serializer.validated_data.get('assignment_id')
        if not assignment_id:
            return Response(
                {'status': 400, 'message': 'assignment_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        assignment = KPIAssignment.objects.get(id=assignment_id)
        
        user = request.user
        
        # Check if user is assigned (either directly or via role)
        if assignment.assignment_type == 'user':
            if assignment.user != user:
                return Response(
                    {'status': 403, 'message': 'You can only create reports for your own KPI assignments.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif assignment.assignment_type == 'role':
            if not user.role or user.role != assignment.role:
                return Response(
                    {'status': 403, 'message': 'You can only create reports for KPIs assigned to your role.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        instance = serializer.save()
        return Response(
            {"status": 201, "data": KPIReportDetailsSerializer(instance).data},
            status=status.HTTP_201_CREATED
        )


class KPIReportDetailView(APIView):
    """Retrieve, update, or delete a KPI report."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get KPI report details."""
        report = get_object_or_404(
            KPIReport.objects.select_related('kpi', 'assignment', 'reported_by', 'approved_by'),
            id=pk
        )
        
        # Check permissions
        user = request.user
        supervisor_role = Role.objects.filter(
            Q(name='Supervisor') | Q(slug__in=['supervisor', 'manager']),
            users=user,
            is_active=True
        ).first()
        
        if not supervisor_role and not user.is_superuser and report.reported_by != user:
            return Response(
                {'status': 403, 'message': 'You can only view your own reports.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = KPIReportDetailsSerializer(report)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)
    
    def put(self, request, pk):
        """Update KPI report - only draft reports can be updated."""
        report = get_object_or_404(KPIReport, id=pk)
        
        # Check permissions
        user = request.user
        if report.reported_by != user:
            return Response(
                {'status': 403, 'message': 'You can only update your own reports.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if report.status != 'draft':
            return Response(
                {'status': 400, 'message': 'Only draft reports can be updated.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = KPIReportCreateSerializer(report, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({"status": 200, "data": KPIReportDetailsSerializer(instance).data}, status=status.HTTP_200_OK)
    
    def patch(self, request, pk):
        """Partially update KPI report - only draft reports can be updated."""
        report = get_object_or_404(KPIReport, id=pk)
        
        # Check permissions
        user = request.user
        if report.reported_by != user:
            return Response(
                {'status': 403, 'message': 'You can only update your own reports.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if report.status != 'draft':
            return Response(
                {'status': 400, 'message': 'Only draft reports can be updated.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = KPIReportCreateSerializer(report, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({"status": 200, "data": KPIReportDetailsSerializer(instance).data}, status=status.HTTP_200_OK)
    
    def delete(self, request, pk):
        """Delete KPI report - only draft reports can be deleted."""
        report = get_object_or_404(KPIReport, id=pk)
        
        # Check permissions
        user = request.user
        if report.reported_by != user:
            return Response(
                {'status': 403, 'message': 'You can only delete your own reports.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if report.status != 'draft':
            return Response(
                {'status': 400, 'message': 'Only draft reports can be deleted.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        report.delete()
        return Response({"status": 204}, status=status.HTTP_204_NO_CONTENT)


class KPIReportSubmitView(APIView):
    """Submit a KPI report for review."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Submit a draft report for supervisor review."""
        report = get_object_or_404(KPIReport, id=pk)
        
        # Check permissions
        user = request.user
        if report.reported_by != user:
            return Response(
                {'status': 403, 'message': 'You can only submit your own reports.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if report.status != 'draft':
            return Response(
                {'status': 400, 'message': 'Only draft reports can be submitted.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        report.submit()
        serializer = KPIReportDetailsSerializer(report)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)


class KPIReportApproveView(APIView):
    """Approve or reject a KPI report (supervisors only)."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Approve or reject a submitted report."""
        report = get_object_or_404(KPIReport, id=pk)
        
        # Check if user is supervisor
        user = request.user
        supervisor_role = Role.objects.filter(
            Q(name='Supervisor') | Q(slug__in=['supervisor', 'manager']),
            users=user,
            is_active=True
        ).first()
        
        if not supervisor_role and not user.is_superuser:
            return Response(
                {'status': 403, 'message': 'Only supervisors can approve/reject reports.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if report.status != 'submitted':
            return Response(
                {'status': 400, 'message': 'Only submitted reports can be approved/rejected.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        action = request.data.get('action')  # 'approve' or 'reject'
        notes = request.data.get('notes', '')
        
        if action == 'approve':
            report.approve(user, notes)
            
            # Trigger aggregation for this KPI period after approval
            # This will aggregate all approved reports for the period and create/update KPIEntry
            try:
                period_start = report.period_start
                period_end = report.period_end
                
                # Try to import and use Celery task if available, otherwise use direct service call
                try:
                    # Call asynchronously via Celery
                    trigger_kpi_aggregation_after_approval.delay(
                        str(report.kpi.id),
                        period_start.isoformat(),
                        period_end.isoformat(),
                        'average'
                    )
                except ImportError:
                    # Fallback to direct service call if Celery is not configured
                    create_kpi_entry_from_approved_reports(
                        kpi=report.kpi,
                        period_start=period_start,
                        period_end=period_end,
                        aggregation_method='average'  # Can be 'sum', 'average', or 'count'
                    )
            except Exception as e:
                # Log error but don't fail the approval
                # The aggregation can be retried via cron job or background task
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to aggregate KPI entry after report approval: {str(e)}")
                
        elif action == 'reject':
            report.reject(user, notes)
        else:
            return Response(
                {'status': 400, 'message': 'Action must be "approve" or "reject".'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = KPIReportDetailsSerializer(report)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)


class KPIApprovalsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get list of KPI reports filtered by status.
        
        Query parameters:
        - status: Filter by status (draft, submitted, approved, rejected). Defaults to 'submitted' if not provided.
        - kpi_id: Filter by specific KPI
        - organization_id: Filter by organization
        - branch_id: Filter by branch
        """
        user = request.user
        
        # Check if user is supervisor
        supervisor_role = Role.objects.filter(
            Q(name='Supervisor') | Q(slug__in=['supervisor', 'manager']),
            users=user,
            is_active=True
        ).first()
        
        if not supervisor_role and not user.is_superuser:
            return Response(
                {'status': 403, 'message': 'Only supervisors can view KPI approvals.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get status filter (default to 'submitted' for backward compatibility)
        status_filter = request.query_params.get('status', 'submitted')
        
        # Validate status
        valid_statuses = ['draft', 'submitted', 'approved', 'rejected']
        if status_filter not in valid_statuses:
            return Response(
                {'status': 400, 'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get reports filtered by status
        queryset = KPIReport.objects.filter(
            status=status_filter
        ).select_related(
            'kpi', 'assignment', 'reported_by', 'approved_by',
            'kpi__organization', 'kpi__branch'
        )
        
        # Optional filters
        kpi_id = request.query_params.get('kpi_id')
        if kpi_id:
            queryset = queryset.filter(kpi__id=kpi_id)
        
        organization_id = request.query_params.get('organization_id')
        if organization_id:
            queryset = queryset.filter(kpi__organization_id=organization_id)
        
        branch_id = request.query_params.get('branch_id')
        if branch_id:
            queryset = queryset.filter(kpi__branch_id=branch_id)
        
        # Order by appropriate date field based on status
        if status_filter == 'submitted':
            # For submitted reports, order by submission date
            queryset = queryset.order_by('-submitted_at', '-period_start', '-created_at')
        elif status_filter in ['approved', 'rejected']:
            # For approved/rejected reports, order by review date
            queryset = queryset.order_by('-reviewed_at', '-period_start', '-created_at')
        else:
            # For draft reports, order by creation date
            queryset = queryset.order_by('-period_start', '-created_at')
        
        serializer = KPIReportDetailsSerializer(queryset, many=True)
        return Response({
            "status": 200,
            "data": serializer.data,
            "count": len(serializer.data),
            "filter_status": status_filter
        }, status=status.HTTP_200_OK)
