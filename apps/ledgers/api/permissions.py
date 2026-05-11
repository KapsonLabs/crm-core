from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAccountingViewer(BasePermission):
    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)


class IsAccountingManager(BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.has_perm("ledgers.manage_accounting"))
        )
