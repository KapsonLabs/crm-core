from datetime import date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kpis.api.mixins import TenantContextMixin
from apps.kpis.api.serializers import (
    DraftVersionCreateSerializer,
    ExecutionTriggerSerializer,
    SnapshotQuerySerializer,
    VersionTransitionSerializer,
)
from apps.kpis.application.factory import (
    build_kpi_definition_service,
    build_kpi_execution_service,
    build_snapshot_reporting_service,
)
from apps.kpis.domain.exceptions import (
    FormulaCompilationError,
    InvalidLifecycleTransition,
    TenantIsolationError,
    VersionNotFound,
)
from apps.kpis.execution.tasks import run_kpi_version


def _error_response(exc: Exception) -> Response:
    if isinstance(exc, TenantIsolationError):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, VersionNotFound):
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, InvalidLifecycleTransition):
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, FormulaCompilationError):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class KpiDraftVersionCreateView(TenantContextMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DraftVersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = self.get_tenant_context(request)
        service = build_kpi_definition_service()
        try:
            result = service.create_draft_version(
                tenant,
                kpi_id=str(serializer.validated_data["kpi_id"]),
                formula=serializer.validated_data["formula"],
            )
        except Exception as exc:
            return _error_response(exc)

        return Response(result, status=status.HTTP_201_CREATED)


class KpiVersionApproveView(TenantContextMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, kpi_id, version):
        serializer = VersionTransitionSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        tenant = self.get_tenant_context(request)
        service = build_kpi_definition_service()
        try:
            result = service.approve_version(
                tenant,
                kpi_id=str(kpi_id),
                version=version,
            )
        except Exception as exc:
            return _error_response(exc)

        return Response(result, status=status.HTTP_200_OK)


class KpiVersionPublishView(TenantContextMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, kpi_id, version):
        serializer = VersionTransitionSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        tenant = self.get_tenant_context(request)
        service = build_kpi_definition_service()
        try:
            result = service.publish_version(
                tenant,
                kpi_id=str(kpi_id),
                version=version,
            )
        except Exception as exc:
            return _error_response(exc)

        return Response(result, status=status.HTTP_200_OK)


class KpiExecutionTriggerView(TenantContextMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ExecutionTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = self.get_tenant_context(request)
        payload = serializer.validated_data
        window = {
            "kind": payload["kind"],
            "start": payload["start"].isoformat(),
            "end": payload["end"].isoformat(),
        }

        version = payload.get("version")
        kpi_id = str(payload["kpi_id"])

        try:
            if payload["run_async"]:
                if version is None:
                    definition_service = build_kpi_definition_service()
                    published = definition_service.get_published_for_date(
                        tenant,
                        kpi_id=kpi_id,
                        as_of=payload["end"],
                    )
                    version = int(published["version"])

                composite_version_id = f"{kpi_id}:{version}"
                task = run_kpi_version.apply_async(
                    kwargs={
                        "organization_id": tenant.organization_id,
                        "kpi_version_id": composite_version_id,
                        "window": window,
                        "trigger": payload["trigger"],
                    },
                    queue="kpi_compute_high",
                )
                return Response(
                    {
                        "task_id": task.id,
                        "kpi_id": kpi_id,
                        "version": version,
                        "window": window,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

            execution_service = build_kpi_execution_service()
            result = execution_service.run(
                tenant,
                kpi_id=kpi_id,
                version=version,
                window=window,
                trigger=payload["trigger"],
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            return _error_response(exc)


class KpiSnapshotListView(TenantContextMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = SnapshotQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        tenant = self.get_tenant_context(request)

        kpi_id = str(serializer.validated_data["kpi_id"])
        start_date: date | None = serializer.validated_data.get("start_date")
        end_date: date | None = serializer.validated_data.get("end_date")

        service = build_snapshot_reporting_service()
        try:
            results = service.list_snapshots(
                tenant,
                kpi_id=kpi_id,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            return _error_response(exc)

        return Response({"count": len(results), "results": results}, status=status.HTTP_200_OK)
