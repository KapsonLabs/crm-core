from apps.organization.models import Organization
from apps.organization.services import resolve_branch_for_user

from .models import Customer, CustomerFeedback


def customers_visible_queryset(user):
    qs = Customer.objects.select_related('organization', 'branch')
    if user.is_job_manager:
        if user.organization_id:
            qs = qs.filter(organization_id=user.organization_id)
        return qs
    if user.organization_id:
        qs = qs.filter(organization_id=user.organization_id)
        if user.branch_id:
            qs = qs.filter(branch_id=user.branch_id)
        return qs
    return qs.none()


def feedback_visible_queryset(user, customer_id=None):
    qs = CustomerFeedback.objects.select_related(
        'customer', 'customer__organization', 'customer__branch', 'submitted_by',
    )
    customer_qs = customers_visible_queryset(user)
    qs = qs.filter(customer_id__in=customer_qs.values('id'))
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    return qs


def create_customer(user, data):
    branch, organization = resolve_branch_for_user(user, data['branch_id'])
    return Customer.objects.create(
        organization=organization,
        branch=branch,
        first_name=data['first_name'],
        last_name=data['last_name'],
        phone_number=data['phone_number'],
        email=data.get('email'),
        is_active=data.get('is_active', True),
    )


def update_customer(instance, user, data, partial=False):
    if not user.is_job_manager:
        if user.organization_id and instance.organization_id != user.organization_id:
            raise PermissionError('You cannot update this customer.')
    if 'organization_id' in data and data['organization_id'] is not None:
        if not user.is_superuser:
            raise ValueError('Only superusers may change customer organization.')
        instance.organization = Organization.objects.get(pk=data['organization_id'])
    for key in ('first_name', 'last_name', 'phone_number', 'email', 'is_active'):
        if key not in data:
            continue
        setattr(instance, key, data[key])
    instance.save()
    return instance


def delete_customer(instance, user):
    if not user.is_job_manager:
        raise PermissionError('Only administrators or supervisors can delete customers.')
    if user.organization_id and not user.is_superuser and instance.organization_id != user.organization_id:
        raise PermissionError('You cannot delete this customer.')
    instance.delete()


def create_feedback(user, data):
    customer = Customer.objects.get(pk=data['customer_id'])
    vis = customers_visible_queryset(user)
    if not vis.filter(pk=customer.pk).exists():
        raise ValueError('Customer not found or not accessible.')
    return CustomerFeedback.objects.create(
        customer=customer,
        submitted_by=user,
        subject=data['subject'],
        body=data['body'],
        rating=data.get('rating'),
    )


def update_feedback(instance, user, data, partial=False):
    vis = feedback_visible_queryset(user)
    if not vis.filter(pk=instance.pk).exists():
        raise ValueError('Feedback not found or not accessible.')
    if not user.is_job_manager and instance.submitted_by_id != user.id:
        raise PermissionError('You can only edit your own feedback.')
    for key in ('subject', 'body', 'rating'):
        if key in data:
            setattr(instance, key, data[key])
    instance.save()
    return instance


def delete_feedback(instance, user):
    if not user.is_job_manager:
        raise PermissionError('Only administrators or supervisors can delete feedback.')
    vis = feedback_visible_queryset(user)
    if not vis.filter(pk=instance.pk).exists():
        raise ValueError('Feedback not found or not accessible.')
    instance.delete()
