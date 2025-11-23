from django.urls import path

from .views import (
    OrganizationListCreateView,
    OrganizationDetailView,
    OrganizationLicenseView,
    BranchListCreateView,
    BranchDetailView,
    BranchSettingsView,
    BranchUserListCreateView,
    BranchUserDetailView,
)


app_name = "organization"

urlpatterns = [
    # Organizations
    path("organizations/", OrganizationListCreateView.as_view(), name="organization-list-create"),
    path("organizations/<uuid:pk>/", OrganizationDetailView.as_view(), name="organization-detail"),

    # Organization License
    path("organizations/license/", OrganizationLicenseView.as_view(), name="organization-license"),

    # Branches
    path("branches/", BranchListCreateView.as_view(), name="branch-list-create"),
    path("branches/<uuid:pk>/", BranchDetailView.as_view(), name="branch-detail"),

    # Branch settings
    path("branches/settings/", BranchSettingsView.as_view(), name="branch-settings"),

    # Branch users
    path("branches/users/", BranchUserListCreateView.as_view(), name="branch-user-list-create"),
    path("branches/users/<uuid:pk>/", BranchUserDetailView.as_view(), name="branch-user-detail"),
]

