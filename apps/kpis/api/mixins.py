from rest_framework.exceptions import PermissionDenied

from apps.kpis.application.contracts import TenantContext


class TenantContextMixin:
    """Builds TenantContext from authenticated user for app-level isolation."""

    def get_tenant_context(self, request) -> TenantContext:
        organization_id = getattr(request.user, "organization_id", None)
        if not organization_id:
            raise PermissionDenied("User does not belong to an organization.")

        request_id = request.headers.get("X-Request-ID")
        user_id = str(request.user.id) if getattr(request.user, "id", None) else None
        return TenantContext(
            organization_id=str(organization_id),
            user_id=user_id,
            request_id=request_id,
        )
