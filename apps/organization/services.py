"""Shared helpers for organization and branch access."""
import logging

from django.db import transaction
from .models import Branch
from apps.ledgers.seed import seed_default_chart_of_accounts, seed_default_payment_methods

logger = logging.getLogger(__name__)


def resolve_branch_for_user(user, branch_id):
    """
    Load a Branch and its Organization, enforcing that the user may use this branch.

    Returns:
        tuple: (branch, organization)

    Raises:
        Branch.DoesNotExist: invalid branch id
        ValueError: user cannot access this branch
    """
    from .models import Branch

    branch = Branch.objects.select_related('organization').get(pk=branch_id)
    organization = branch.organization

    if user.is_superuser:
        return branch, organization

    if not user.organization_id:
        raise ValueError('Your account must belong to an organization.')

    if str(branch.organization_id) != str(user.organization_id):
        raise ValueError('Branch does not belong to your organization.')

    return branch, organization


@transaction.atomic
def create_branch(organization, data: dict):
    """
    Create a Branch and seed its chart of accounts using the organization's business_type.

    The accounting seed runs inside the same transaction — if seeding fails the
    branch row is also rolled back, keeping accounting and operational data in sync.
    """
    

    branch = Branch.objects.create(
        organization=organization,
        name=data['name'],
        code=data['code'],
        email=data.get('email'),
        phone_number=data.get('phone_number'),
        address=data.get('address', ''),
        city=data.get('city', ''),
        country=data.get('country', ''),
        is_active=data.get('is_active', True),
    )

    business_type = organization.business_type or 'general'
    seed_default_chart_of_accounts(branch=branch.id, business_type=business_type)
    logger.info(
        "Seeded '%s' chart of accounts for branch %s (%s)",
        business_type,
        branch.id,
        branch.name,
    )

    seed_default_payment_methods(branch_id=branch.id)
    logger.info("Seeded default payment methods for branch %s (%s)", branch.id, branch.name)

    return branch
