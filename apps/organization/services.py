"""Shared helpers for organization and branch access."""


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
