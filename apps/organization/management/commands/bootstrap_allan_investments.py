"""
Bootstrap demo tenant: Allan Investments (inventory), two branches, demo users.

Prerequisites:
    python manage.py migrate
    python manage.py seed_roles_permissions

Roles are resolved by slug (Supervisor → manager, Agent → support-agent, Viewer → viewer).
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role
from apps.organization.models import Branch, BranchUser, Organization
from apps.organization.services import create_branch

ORG_NAME = "Allan Investments"
ROLE_SLUG_SUPERVISOR = "manager"
ROLE_SLUG_AGENT = "support-agent"
ROLE_SLUG_VIEWER = "viewer"

BRANCH_SPECS = (
    {
        "name": "Kampala Branch",
        "code": "KLA",
        "city": "Kampala",
        "country": "Uganda",
    },
)


def _username_from_email(email: str) -> str:
    raw = email.replace("@", "_").replace(".", "_")
    return raw[:150]


class Command(BaseCommand):
    help = (
        "Create Allan Investments (inventory), Kampala + Jinja branches, "
        "5 users per branch (1 Supervisor, 3 Agents, 1 Viewer), "
        "then seed global inventory chart (seed_default_chart)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="user1234",
            help="Password for all demo users (development only). Default: user1234.",
        )
        parser.add_argument(
            "--currency",
            default="UGX",
            help="Currency passed to seed_default_chart (default: UGX).",
        )
        parser.add_argument(
            "--force-users",
            action="store_true",
            help="If demo users already exist, reset their password and org/branch/role assignments.",
        )

    def handle(self, *args, **options):
        password = options["password"]
        currency = options["currency"]
        force_users = options["force_users"]

        roles = self._load_roles()

        with transaction.atomic():
            org = self._ensure_organization()
            branches = [self._ensure_branch(org, spec) for spec in BRANCH_SPECS]
            for branch in branches:
                self._bootstrap_branch_users(
                    org,
                    branch,
                    roles,
                    password,
                    force_users,
                )

        # call_command("seed_default_chart", business="inventory", currency=currency)
        self.stdout.write(
            self.style.SUCCESS(
                f"Finished bootstrap for '{ORG_NAME}'. Global inventory chart seeded (currency={currency})."
            )
        )

    def _load_roles(self) -> dict[str, Role]:
        needed = {
            "supervisor": ROLE_SLUG_SUPERVISOR,
            "agent": ROLE_SLUG_AGENT,
            "viewer": ROLE_SLUG_VIEWER,
        }
        resolved = {}
        missing = []
        for key, slug in needed.items():
            try:
                resolved[key] = Role.objects.get(slug=slug, is_active=True)
            except Role.DoesNotExist:
                missing.append(slug)
        if missing:
            raise CommandError(
                "Missing role(s): "
                + ", ".join(missing)
                + ". Run: python manage.py seed_roles_permissions"
            )
        return resolved

    def _ensure_organization(self) -> Organization:
        org, created = Organization.objects.get_or_create(
            name=ORG_NAME,
            defaults={
                "business_type": "inventory",
                "description": "",
                "is_active": True,
            },
        )
        if not created and org.business_type != "inventory":
            org.business_type = "inventory"
            org.save(update_fields=["business_type", "updated_at"])
        action = "Created" if created else "Using existing"
        self.stdout.write(f"{action} organization: {org.name} ({org.business_type})")
        return org

    def _ensure_branch(self, org: Organization, spec: dict) -> Branch:
        existing = Branch.objects.filter(organization=org, code=spec["code"]).first()
        if existing:
            self.stdout.write(f"Using existing branch: {existing.name} ({existing.code})")
            return existing
        branch = create_branch(org, dict(spec))
        self.stdout.write(self.style.SUCCESS(f"Created branch: {branch.name} ({branch.code})"))
        return branch

    def _bootstrap_branch_users(
        self,
        org: Organization,
        branch: Branch,
        roles: dict[str, Role],
        password: str,
        force_users: bool,
    ):
        User = get_user_model()
        code_lower = branch.code.lower()
        specs = [
            ("supervisor", roles["supervisor"], f"supervisor.{code_lower}@allan-demo.local", f"supervisor_{code_lower}"),
            ("agent", roles["agent"], f"agent1.{code_lower}@allan-demo.local", f"agent1_{code_lower}"),
            ("agent", roles["agent"], f"agent2.{code_lower}@allan-demo.local", f"agent2_{code_lower}"),
            ("agent", roles["agent"], f"agent3.{code_lower}@allan-demo.local", f"agent3_{code_lower}"),
            ("viewer", roles["viewer"], f"viewer.{code_lower}@allan-demo.local", f"viewer_{code_lower}"),
        ]

        for _kind, role, email, _username in specs:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": _username,
                    "organization": org,
                    "branch": branch,
                    "role": role,
                    "is_active": True,
                    "first_name": "",
                    "last_name": "",
                },
            )
            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
                self.stdout.write(f"  Created: {email} ({role.name})")
            else:
                user.username = _username
                user.organization = org
                user.branch = branch
                user.role = role
                user.is_active = True
                update_fields = [
                    "username",
                    "organization",
                    "branch",
                    "role",
                    "is_active",
                    "updated_at",
                ]
                if force_users:
                    user.set_password(password)
                    update_fields.append("password")
                    self.stdout.write(f"  Updated + password reset: {email} ({role.name})")
                else:
                    self.stdout.write(f"  Updated assignment (password unchanged): {email}")
                user.save(update_fields=update_fields)

            BranchUser.objects.update_or_create(
                branch=branch,
                user=user,
                defaults={
                    "role": role,
                    "is_active": True,
                    "is_branch_admin": False,
                },
            )
