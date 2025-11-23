import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import Role


class Organization(models.Model):
    """Represents a top-level organization (e.g., company or NGO)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=25, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    physical_address = models.CharField(max_length=500, blank=True)
    logo = models.ImageField(upload_to="organization_logos/%Y/%m/%d/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class OrganizationLicense(models.Model):
    """Stores licensing information for an organization."""

    PLAN_CHOICES = [
        ("starter", "Starter"),
        ("standard", "Standard"),
        ("premium", "Premium"),
        ("enterprise", "Enterprise"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("pending", "Pending"),
        ("expired", "Expired"),
        ("suspended", "Suspended"),
    ]

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="license",
        primary_key=True,
    )
    license_key = models.CharField(max_length=255, unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="starter")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    seats = models.PositiveIntegerField(default=5, help_text="Maximum number of active users allowed.")
    starts_on = models.DateField()
    expires_on = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("organization license")
        verbose_name_plural = _("organization licenses")

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.license_key}"

    @property
    def is_active(self) -> bool:

        today = timezone.now().date()
        return self.status == "active" and self.starts_on <= today <= self.expires_on


class Branch(models.Model):
    """Represents a branch under an organization."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="branches",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, help_text="Short unique code for the branch.")
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=25, blank=True, null=True)
    address = models.CharField(max_length=500, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True, default="")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("branch")
        verbose_name_plural = _("branches")
        unique_together = ("organization", "code")
        ordering = ["organization__name", "name"]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.name}"


class BranchSettings(models.Model):
    """Configuration settings specific to a branch."""

    branch = models.OneToOneField(
        Branch,
        on_delete=models.CASCADE,
        related_name="settings",
    )
    timezone = models.CharField(max_length=50, default="UTC")
    currency = models.CharField(max_length=10, default="USD")
    date_format = models.CharField(max_length=20, default="YYYY-MM-DD")
    language = models.CharField(max_length=10, default="en")
    working_hours_start = models.TimeField(blank=True, null=True)
    working_hours_end = models.TimeField(blank=True, null=True)
    allow_weekend_operations = models.BooleanField(default=False)

    notifications_email = models.EmailField(blank=True, null=True)
    notifications_phone = models.CharField(max_length=25, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("branch settings")
        verbose_name_plural = _("branch settings")

    def __str__(self) -> str:
        return f"Settings for {self.branch}"


class BranchUser(models.Model):
    """Associates users with branches and optional roles."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="branch_users",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_branches",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="branch_users",
    )
    is_branch_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="branch_assignments_made",
    )

    class Meta:
        verbose_name = _("branch user")
        verbose_name_plural = _("branch users")
        unique_together = ("branch", "user")
        ordering = ["branch__organization__name", "branch__name", "user__email"]
        indexes = [
            models.Index(fields=["branch", "is_active"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} @ {self.branch}"

    def clean(self):

        if self.role and not self.role.is_active:
            raise ValidationError(_("Assigned role must be active."))

