from django.contrib import admin

from .models import (
    Organization,
    OrganizationLicense,
    Branch,
    BranchSettings,
    BranchUser,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone_number", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "email", "phone_number")
    ordering = ("name",)


@admin.register(OrganizationLicense)
class OrganizationLicenseAdmin(admin.ModelAdmin):
    list_display = ("organization", "license_key", "plan", "status", "starts_on", "expires_on")
    list_filter = ("plan", "status", "starts_on", "expires_on")
    search_fields = ("organization__name", "license_key")
    ordering = ("-starts_on",)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "code", "city", "country", "is_active", "created_at")
    list_filter = ("organization", "is_active", "country")
    search_fields = ("name", "code", "organization__name", "city", "country")
    ordering = ("organization__name", "name")


@admin.register(BranchSettings)
class BranchSettingsAdmin(admin.ModelAdmin):
    list_display = ("branch", "timezone", "currency", "date_format", "language")
    list_filter = ("timezone", "currency", "language")
    search_fields = ("branch__name", "branch__organization__name")


@admin.register(BranchUser)
class BranchUserAdmin(admin.ModelAdmin):
    list_display = ("user", "branch", "role", "is_branch_admin", "is_active", "assigned_at")
    list_filter = ("branch__organization", "branch", "role", "is_branch_admin", "is_active")
    search_fields = ("user__email", "branch__name", "branch__organization__name", "role__name")
    raw_id_fields = ("user", "assigned_by", "branch", "role")

