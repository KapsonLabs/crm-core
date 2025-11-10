from django.urls import path
from .views import (
    # Authentication views
    LoginView,
    RefreshTokenView,
    VerifyTokenView,
    LogoutView,
    # User views
    UserListView,
    UserDetailView,
    UserUpdateView,
    UserDeactivateView,
    UserActivateView,
    ChangePasswordView,
    CurrentUserView,
    CurrentUserPermissionsView,
    # Module views
    ModuleListView,
    ModuleDetailView,
    # Permission views
    PermissionListCreateView,
    PermissionDetailView,
    # Role views
    RoleListCreateView,
    RoleDetailView,
)

urlpatterns = [
    # Authentication endpoints
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
    path("auth/verify/", VerifyTokenView.as_view(), name="auth-verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    
    # User endpoints
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/me/", CurrentUserView.as_view(), name="current-user"),
    path("users/me/permissions/", CurrentUserPermissionsView.as_view(), name="current-user-permissions"),
    path("users/<uuid:user_id>/", UserDetailView.as_view(), name="user-detail"),
    path("users/<uuid:user_id>/update/", UserUpdateView.as_view(), name="user-update"),
    path("users/<uuid:user_id>/deactivate/", UserDeactivateView.as_view(), name="user-deactivate"),
    path("users/<uuid:user_id>/activate/", UserActivateView.as_view(), name="user-activate"),
    path("users/change-password/", ChangePasswordView.as_view(), name="change-password"),
    
    # Module endpoints
    path("modules/", ModuleListView.as_view(), name="module-list"),
    path("modules/<int:module_id>/", ModuleDetailView.as_view(), name="module-detail"),
    
    # Permission endpoints
    path("permissions/", PermissionListCreateView.as_view(), name="permission-list-create"),
    path("permissions/<uuid:permission_id>/", PermissionDetailView.as_view(), name="permission-detail"),
    
    # Role endpoints
    path("roles/", RoleListCreateView.as_view(), name="role-list-create"),
    path("roles/<uuid:role_id>/", RoleDetailView.as_view(), name="role-detail"),
]

