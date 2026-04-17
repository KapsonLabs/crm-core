from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from .models import Job, JobAssignment, JobProduct, Product

_MISSING = object()


def is_job_manager(user):
    if user.is_superuser or user.is_staff:
        return True
    from apps.accounts.models import Role
    return Role.objects.filter(
        Q(name='Supervisor') | Q(slug__in=['supervisor', 'manager']),
        users=user,
        is_active=True,
    ).exists()


def products_visible_for_user(user):
    qs = Product.objects.select_related('organization')
    if is_job_manager(user):
        if user.organization_id:
            return qs.filter(organization_id=user.organization_id)
        return qs
    if user.organization_id:
        return qs.filter(organization_id=user.organization_id)
    return qs.none()


def create_product(user, data):
    from apps.organization.models import Organization

    name = data['name']
    kind = data['kind']
    description = data.get('description', '')
    price = Decimal(str(data['price']))
    is_active = data.get('is_active', True)
    org_raw = data.get('organization_id', _MISSING)

    if org_raw is _MISSING:
        if user.is_superuser and user.organization_id:
            organization = Organization.objects.get(pk=user.organization_id)
        elif user.is_superuser:
            raise ValueError('organization_id is required when the user has no organization.')
        else:
            if not user.organization_id:
                raise ValueError('Your account must belong to an organization.')
            organization = Organization.objects.get(pk=user.organization_id)
    else:
        if not user.is_superuser and str(user.organization_id) != str(org_raw):
            raise ValueError('You may only create products for your organization.')
        organization = Organization.objects.get(pk=org_raw)

    return Product.objects.create(
        organization=organization,
        kind=kind,
        name=name,
        description=description,
        price=price,
        is_active=is_active,
    )


def update_product(instance, user, data, partial=False):
    from apps.organization.models import Organization

    if not is_job_manager(user):
        raise PermissionError('Only administrators or supervisors can update products.')
    if 'organization_id' in data:
        oid = data['organization_id']
        if oid is not None:
            if not user.is_superuser and str(user.organization_id) != str(oid):
                raise ValueError('You may only assign products to your organization.')
            instance.organization = Organization.objects.get(pk=oid)
    for key in ('kind', 'name', 'description', 'is_active'):
        if key in data:
            setattr(instance, key, data[key])
    if 'price' in data and data['price'] is not None:
        instance.price = Decimal(str(data['price']))
    instance.save()
    return instance


def delete_product(instance, user):
    if not is_job_manager(user):
        raise PermissionError('Only administrators or supervisors can delete products.')
    if user.organization_id and not user.is_superuser and instance.organization_id != user.organization_id:
        raise PermissionError('You cannot delete this product.')
    if JobProduct.objects.filter(product=instance).exists():
        raise ValueError('Cannot delete a product that is attached to jobs.')
    instance.delete()


def job_queryset_for_user(user):
    qs = Job.objects.select_related(
        'customer',
        'organization',
        'branch',
        'created_by',
        'completed_by',
        'closed_by',
    ).prefetch_related(
        'assignments__user',
        'job_products__product',
    )
    if is_job_manager(user):
        if user.organization_id:
            return qs.filter(organization_id=user.organization_id)
        return qs
    return qs.filter(
        Q(created_by=user) | Q(assignments__user=user)
    ).distinct()


def _build_job_product_lines(job, organization_id, items):
    if not items:
        return []
    seen = set()
    product_ids = []
    for item in items:
        pid = item['product_id']
        sid = str(pid)
        if sid in seen:
            raise ValueError('Duplicate product_id in job_products is not allowed.')
        seen.add(sid)
        product_ids.append(pid)

    products = list(
        Product.objects.filter(
            id__in=product_ids,
            organization_id=organization_id,
            is_active=True,
        )
    )
    if len(products) != len(product_ids):
        raise ValueError(
            'One or more products are invalid, inactive, or not in the job organization.',
        )
    by_id = {str(p.id): p for p in products}
    lines = []
    for item in items:
        p = by_id[str(item['product_id'])]
        qty_raw = item.get('quantity')
        quantity = Decimal(str(qty_raw)) if qty_raw is not None else Decimal('1')
        if quantity <= 0:
            raise ValueError('Quantity must be greater than zero.')
        if item.get('unit_price') is not None:
            unit_price = Decimal(str(item['unit_price']))
        else:
            unit_price = p.price
        line_total = (quantity * unit_price).quantize(Decimal('0.01'))
        lines.append(
            JobProduct(
                job=job,
                product=p,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )
    return lines


def create_job(user, data):
    from apps.customers.models import Customer
    from apps.organization.models import Organization, Branch

    raw = dict(data)
    job_products_data = raw.pop('job_products', None)
    if job_products_data is None:
        job_products_data = []

    customer_id = raw['customer_id']
    branch_id = raw.get('branch_id')
    org_id = raw.get('organization_id')
    status = raw.get('status', Job.STATUS_OPEN)
    title = raw['title']
    description = raw.get('description', '')

    if status in (Job.STATUS_COMPLETED, Job.STATUS_CLOSED):
        raise ValueError('Use the complete or close endpoints for this status.')

    customer = Customer.objects.get(pk=customer_id)

    if user.is_superuser:
        if org_id:
            organization = Organization.objects.get(pk=org_id)
        elif user.organization_id:
            organization = Organization.objects.get(pk=user.organization_id)
        else:
            organization = Organization.objects.get(pk=customer.organization_id)
    else:
        if not user.organization_id:
            raise ValueError('Your account must belong to an organization to create jobs.')
        organization = Organization.objects.get(pk=user.organization_id)

    if customer.organization_id != organization.id:
        raise ValueError('Customer must belong to the same organization as the job.')

    branch = None
    if branch_id:
        branch = Branch.objects.get(pk=branch_id, organization=organization)

    with transaction.atomic():
        job = Job.objects.create(
            customer=customer,
            organization=organization,
            branch=branch,
            created_by=user,
            title=title,
            description=description,
            status=status,
        )
        lines = _build_job_product_lines(job, organization.id, job_products_data)
        if lines:
            JobProduct.objects.bulk_create(lines)

    return job


def update_job(user, instance, data, partial=False):
    from apps.customers.models import Customer
    from apps.organization.models import Branch

    data = {k: v for k, v in data.items() if k not in ('organization_id', 'job_products')}

    if not is_job_manager(user) and instance.created_by_id != user.id:
        raise PermissionError('You can only edit jobs you created.')
    if not is_job_manager(user):
        if instance.status not in (Job.STATUS_OPEN, Job.STATUS_IN_PROGRESS):
            raise PermissionError('You cannot edit a job that is completed or closed.')

    if 'status' in data:
        st = data['status']
        if st in (Job.STATUS_COMPLETED, Job.STATUS_CLOSED):
            raise ValueError('Use the complete or close endpoints for this status.')

    if 'customer_id' in data:
        customer = Customer.objects.get(pk=data['customer_id'])
        if customer.organization_id != instance.organization_id:
            raise ValueError('Customer must belong to the same organization as the job.')
        instance.customer = customer

    if 'branch_id' in data:
        bid = data['branch_id']
        if bid is None:
            instance.branch = None
        else:
            instance.branch = Branch.objects.get(pk=bid, organization_id=instance.organization_id)

    for attr in ('title', 'description', 'status'):
        if attr in data:
            setattr(instance, attr, data[attr])

    instance.save()
    return instance


def assign_users_to_job(job, user_ids, assigned_by):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if not user_ids:
        return [], []
    org_id = job.organization_id
    users = list(
        User.objects.filter(id__in=user_ids, organization_id=org_id, is_active=True)
    )
    found_ids = {str(u.id) for u in users}
    requested = {str(uid) for uid in user_ids}
    missing = list(requested - found_ids)
    created = []
    for u in users:
        obj, _ = JobAssignment.objects.get_or_create(
            job=job,
            user=u,
            defaults={'assigned_by': assigned_by},
        )
        created.append(obj)
    return created, missing


def complete_job(job, user, notes=''):
    if job.status == Job.STATUS_CLOSED:
        raise ValueError('Cannot complete a closed job.')
    if job.status == Job.STATUS_COMPLETED:
        return job
    job.status = Job.STATUS_COMPLETED
    from django.utils import timezone
    job.completed_at = timezone.now()
    job.completed_by = user
    if notes:
        job.completion_notes = notes
    job.save()
    return job


def close_job(job, user, notes=''):
    if job.status == Job.STATUS_CLOSED:
        return job
    job.status = Job.STATUS_CLOSED
    from django.utils import timezone
    job.closed_at = timezone.now()
    job.closed_by = user
    if notes:
        job.closing_notes = notes
    job.save()
    return job
