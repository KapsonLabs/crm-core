from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from .models import Job, JobAssignment, JobProduct, Product
from apps.organization.models import Organization, Branch
from apps.organization.services import resolve_branch_for_user
from apps.customers.models import Customer
from django.utils import timezone


def products_visible_for_user(user):
    qs = Product.objects.select_related('organization', 'branch')
    if user.is_job_manager:
        if user.organization_id:
            return qs.filter(organization_id=user.organization_id)
        return qs
    if user.organization_id:
        qs = qs.filter(organization_id=user.organization_id)
        if user.branch_id:
            qs = qs.filter(branch_id=user.branch_id)
        return qs
    return qs.none()


def create_product(user, data):
    branch, organization = resolve_branch_for_user(user, data['branch_id'])
    name = data['name']
    kind = data['kind']
    description = data.get('description', '')
    price = Decimal(str(data['price']))
    is_active = data.get('is_active', True)

    return Product.objects.create(
        organization=organization,
        branch=branch,
        kind=kind,
        name=name,
        description=description,
        price=price,
        is_active=is_active,
    )


def update_product(instance, user, data, partial=False):

    if not user.is_job_manager:
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
    if not user.is_job_manager:
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
    if user.is_job_manager:
        if user.organization_id:
            return qs.filter(organization_id=user.organization_id)
        return qs
    return qs.filter(
        Q(created_by=user) | Q(assignments__user=user)
    ).distinct()


def _build_job_product_lines(job, items):
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

    q = Product.objects.filter(
        id__in=product_ids,
        organization_id=job.organization_id,
        is_active=True,
    )
    if job.branch_id:
        q = q.filter(branch_id=job.branch_id)
    products = list(q)
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

    raw = dict(data)
    job_products_data = raw.pop('job_products', None)
    if job_products_data is None:
        job_products_data = []
    user_ids = raw.pop('user_ids', None) or []

    customer_id = raw['customer_id']
    branch_id = raw.get('branch_id')
    org_id = raw.get('organization_id')
    status = raw.get('status', Job.STATUS_OPEN)
    title = raw['title']
    description = raw.get('description', '')
    phone_number = raw.get('phone_number', '')

    if status in (Job.STATUS_COMPLETED, Job.STATUS_CLOSED):
        raise ValueError('Use the complete or close endpoints for this status.')

    customer = Customer.objects.get(pk=customer_id)

    branch = None
    organization = None

    if branch_id:
        branch = Branch.objects.select_related('organization').get(pk=branch_id)
        organization = branch.organization
        if org_id and str(organization.id) != str(org_id):
            raise ValueError('organization_id does not match the branch organization.')
        if not user.is_superuser:
            if not user.organization_id:
                raise ValueError('Your account must belong to an organization to create jobs.')
            if str(branch.organization_id) != str(user.organization_id):
                raise ValueError('Branch does not belong to your organization.')
    elif user.is_superuser:
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

    if branch and customer.branch_id != branch.id:
        raise ValueError('Customer must belong to the same branch as the job.')

    with transaction.atomic():
        job = Job.objects.create(
            customer=customer,
            organization=organization,
            branch=branch,
            created_by=user,
            title=title,
            description=description,
            phone_number=phone_number,
            status=status,
        )
        lines = _build_job_product_lines(job, job_products_data)
        if lines:
            JobProduct.objects.bulk_create(lines)
        subtotal = sum((line.line_total for line in lines), Decimal('0.00'))
        from apps.financials.services import create_invoice

        inv_payload = {
            'job_id': job.id,
            'subtotal': subtotal,
            'tax_amount': Decimal('0.00'),
        }
        if job.branch_id:
            inv_payload['branch_id'] = job.branch_id
        create_invoice(user, inv_payload)
        _, missing_user_ids = assign_users_to_job(job, user_ids, user)

    return job, missing_user_ids


def update_job(user, instance, data, partial=False):

    data = {
        k: v
        for k, v in data.items()
        if k not in ('organization_id', 'job_products', 'user_ids')
    }

    if not user.is_job_manager and instance.created_by_id != user.id:
        raise PermissionError('You can only edit jobs you created.')
    if not user.is_job_manager:
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
        if instance.branch_id and customer.branch_id != instance.branch_id:
            raise ValueError('Customer must belong to the same branch as the job.')
        instance.customer = customer

    if 'branch_id' in data:
        bid = data['branch_id']
        if bid is None:
            instance.branch = None
        else:
            instance.branch = Branch.objects.get(pk=bid, organization_id=instance.organization_id)

    for attr in ('title', 'description', 'status', 'phone_number'):
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
    job.closed_at = timezone.now()
    job.closed_by = user
    if notes:
        job.closing_notes = notes
    job.save()
    return job
