from django.db.models import Q

from apps.organization.models import Organization

from .models import Customer, CustomerFeedback


def is_customer_manager(user):
    if user.is_superuser or user.is_staff:
        return True
    from apps.accounts.models import Role
    return Role.objects.filter(
        Q(name='Supervisor') | Q(slug__in=['supervisor', 'manager']),
        users=user,
        is_active=True,
    ).exists()


def customers_visible_queryset(user):
    qs = Customer.objects.select_related('organization')
    if is_customer_manager(user):
        if user.organization_id:
            return qs.filter(organization_id=user.organization_id)
        return qs
    if user.organization_id:
        return qs.filter(organization_id=user.organization_id)
    return qs.none()


def feedback_visible_queryset(user, customer_id=None):
    qs = CustomerFeedback.objects.select_related(
        'customer', 'customer__organization', 'submitted_by',
    )
    customer_qs = customers_visible_queryset(user)
    qs = qs.filter(customer_id__in=customer_qs.values('id'))
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    return qs


def _resolve_organization_for_write(user, organization_id):
    if user.is_superuser and organization_id:
        return Organization.objects.get(pk=organization_id)
    if user.is_superuser and user.organization_id:
        return Organization.objects.get(pk=user.organization_id)
    if not user.organization_id:
        raise ValueError('Your account must belong to an organization.')
    return Organization.objects.get(pk=user.organization_id)


def create_customer(user, data):
    org_id = data.get('organization_id')
    organization = _resolve_organization_for_write(user, org_id)
    if not user.is_superuser and org_id and str(organization.id) != str(org_id):
        raise ValueError('You may only create customers for your organization.')
    return Customer.objects.create(
        organization=organization,
        first_name=data['first_name'],
        last_name=data['last_name'],
        phone_number=data['phone_number'],
        email=data.get('email'),
        is_active=data.get('is_active', True),
    )


def update_customer(instance, user, data, partial=False):
    if not is_customer_manager(user):
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
    if not is_customer_manager(user):
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
    if not is_customer_manager(user) and instance.submitted_by_id != user.id:
        raise PermissionError('You can only edit your own feedback.')
    for key in ('subject', 'body', 'rating'):
        if key in data:
            setattr(instance, key, data[key])
    instance.save()
    return instance


def delete_feedback(instance, user):
    if not is_customer_manager(user):
        raise PermissionError('Only administrators or supervisors can delete feedback.')
    vis = feedback_visible_queryset(user)
    if not vis.filter(pk=instance.pk).exists():
        raise ValueError('Feedback not found or not accessible.')
    instance.delete()
