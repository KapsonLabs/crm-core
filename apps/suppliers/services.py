from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Prefetch, Sum
from django.utils import timezone

from apps.financials.models import Requisition
from apps.jobs.models import Job, Product
from apps.jobs.services import job_queryset_for_user, products_visible_for_user
from apps.organization.models import Organization
from apps.organization.services import resolve_branch_for_user

from .models import LocalPurchaseOrder, LocalPurchaseOrderItem, Supplier


def suppliers_visible_queryset(user):
    qs = Supplier.objects.select_related('organization', 'branch')
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


def active_lpo_items_qs(lpo):
    return LocalPurchaseOrderItem.objects.filter(lpo=lpo, deleted_status=False)


def _sync_item_delivered_from_quantities(item):
    item.delivered_status = item.quantity_received >= item.quantity


def lpos_visible_queryset(user):
    items_qs = LocalPurchaseOrderItem.objects.filter(deleted_status=False).select_related('product')
    qs = LocalPurchaseOrder.objects.select_related(
        'organization',
        'branch',
        'supplier',
        'created_by',
        'approved_by',
        'job',
        'requisition',
    ).prefetch_related(Prefetch('items', queryset=items_qs))
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


def _next_lpo_number(organization_id):
    today = timezone.now().date().strftime('%Y%m%d')
    prefix = f'LPO-{today}-'
    last = LocalPurchaseOrder.objects.filter(
        organization_id=organization_id,
        lpo_number__startswith=prefix,
    ).aggregate(m=Max('lpo_number'))
    max_num = last['m']
    if max_num:
        try:
            n = int(max_num.split('-')[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    else:
        n = 1
    return f'{prefix}{n:04d}'


def refresh_lpo_totals(lpo):
    agg = active_lpo_items_qs(lpo).aggregate(s=Sum('line_total'))
    subtotal = agg['s'] or Decimal('0.00')
    lpo.subtotal = subtotal
    lpo.total = subtotal
    lpo.save(update_fields=('subtotal', 'total', 'updated_at'))
    return lpo


def _item_line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(Decimal('0.01'))


def create_supplier(user, data):
    branch_id = data.get('branch_id')
    if branch_id:
        branch, organization = resolve_branch_for_user(user, branch_id)
    else:
        if not user.organization_id:
            raise ValueError('branch_id is required when your account has no organization.')
        organization = Organization.objects.get(pk=user.organization_id)
        branch = None
    return Supplier.objects.create(
        organization=organization,
        branch=branch,
        name=data['name'],
        contact_name=data.get('contact_name') or '',
        email=data.get('email'),
        phone_number=data.get('phone_number') or '',
        physical_address=data.get('physical_address') or '',
        tax_id=data.get('tax_id') or '',
        payment_terms=data.get('payment_terms') or '',
        notes=data.get('notes') or '',
        is_active=data.get('is_active', True),
    )


def update_supplier(instance, user, data, partial=False):
    if not user.is_job_manager:
        if user.organization_id and instance.organization_id != user.organization_id:
            raise PermissionError('You cannot update this supplier.')
    if 'organization_id' in data and data['organization_id'] is not None:
        if not user.is_superuser:
            raise ValueError('Only superusers may change supplier organization.')
        instance.organization = Organization.objects.get(pk=data['organization_id'])
    if 'branch_id' in data:
        if data['branch_id'] is None:
            instance.branch = None
        else:
            branch, _ = resolve_branch_for_user(user, data['branch_id'])
            if branch.organization_id != instance.organization_id:
                raise ValueError('Branch organization does not match supplier organization.')
            instance.branch = branch
    for key in (
        'name',
        'contact_name',
        'email',
        'phone_number',
        'physical_address',
        'tax_id',
        'payment_terms',
        'notes',
        'is_active',
    ):
        if key not in data:
            continue
        setattr(instance, key, data[key])
    instance.save()
    return instance


def delete_supplier(instance, user):
    if not user.is_job_manager:
        raise PermissionError('Only administrators or supervisors can delete suppliers.')
    if user.organization_id and not user.is_superuser and instance.organization_id != user.organization_id:
        raise PermissionError('You cannot delete this supplier.')
    if instance.local_purchase_orders.exists():
        raise ValueError('Cannot delete a supplier that has LPOs.')
    instance.delete()


def _resolve_supplier_for_user(user, supplier_id):
    supplier = Supplier.objects.get(pk=supplier_id)
    vis = suppliers_visible_queryset(user)
    if not vis.filter(pk=supplier.pk).exists():
        raise ValueError('Supplier not found or not accessible.')
    return supplier


def _validate_product_for_lpo(user, product_id, organization_id):
    if not product_id:
        return None
    try:
        product = products_visible_for_user(user).get(pk=product_id)
    except Product.DoesNotExist as e:
        raise ValueError('Product not found or not accessible.') from e
    if str(product.organization_id) != str(organization_id):
        raise ValueError('Product does not belong to this LPO organization.')
    return product


def create_lpo(user, data):
    supplier = _resolve_supplier_for_user(user, data['supplier_id'])
    branch = None
    organization = supplier.organization
    if data.get('branch_id') is not None:
        branch, org2 = resolve_branch_for_user(user, data['branch_id'])
        if org2.id != organization.id:
            raise ValueError('Branch does not match supplier organization.')
        organization = org2
    job = None
    if data.get('job_id'):
        job = job_queryset_for_user(user).get(pk=data['job_id'])
        if job.organization_id != organization.id:
            raise ValueError('Job organization does not match.')
    requisition = None
    if data.get('requisition_id'):
        requisition = Requisition.objects.get(pk=data['requisition_id'])
        if requisition.organization_id != organization.id:
            raise ValueError('Requisition organization does not match.')

    lpo = LocalPurchaseOrder.objects.create(
        organization=organization,
        branch=branch,
        supplier=supplier,
        job=job,
        requisition=requisition,
        currency=data.get('currency', 'UGX'),
        notes=data.get('notes') or '',
        expected_delivery_date=data.get('expected_delivery_date'),
        created_by=user,
        status=LocalPurchaseOrder.STATUS_DRAFT,
    )
    return lpo


@transaction.atomic
def create_lpo_with_items(user, validated_data):
    """
    Create LPO header and all line items in one transaction.
    validated_data contains header keys plus ``items`` (list of validated line dicts).
    """
    data = validated_data.copy()
    items_data = [dict(item) for item in data.pop('items')]
    lpo = create_lpo(user, data)
    for row in items_data:
        create_lpo_item(lpo, user, row, defer_refresh=True)
    refresh_lpo_totals(lpo)
    return lpo


def update_lpo_header(lpo, user, data, partial=False):
    if lpo.status != LocalPurchaseOrder.STATUS_DRAFT:
        allowed = {'notes', 'expected_delivery_date', 'currency'}
        if not partial:
            extra = set(data.keys()) - allowed
            if extra:
                raise ValueError('Only notes, expected_delivery_date, and currency can change after draft.')
        else:
            for k in data:
                if k not in allowed:
                    raise ValueError(
                        f'Cannot change {k} when LPO is not draft.',
                    )
    if lpo.status == LocalPurchaseOrder.STATUS_DRAFT:
        if 'supplier_id' in data and data['supplier_id'] is not None:
            supplier = _resolve_supplier_for_user(user, data['supplier_id'])
            lpo.supplier = supplier
            if lpo.organization_id != supplier.organization_id:
                raise ValueError('Supplier belongs to another organization.')
        if data.get('branch_id') is not None:
            branch, org = resolve_branch_for_user(user, data['branch_id'])
            if org.id != lpo.organization_id:
                raise ValueError('Branch organization mismatch.')
            lpo.branch = branch
        if 'job_id' in data:
            jid = data['job_id']
            if jid is None:
                lpo.job = None
            else:
                job = job_queryset_for_user(user).get(pk=jid)
                if job.organization_id != lpo.organization_id:
                    raise ValueError('Job organization mismatch.')
                lpo.job = job
        if 'requisition_id' in data:
            rid = data['requisition_id']
            if rid is None:
                lpo.requisition = None
            else:
                req = Requisition.objects.get(pk=rid)
                if req.organization_id != lpo.organization_id:
                    raise ValueError('Requisition organization mismatch.')
                lpo.requisition = req

    if 'notes' in data:
        lpo.notes = data['notes'] or ''
    if 'expected_delivery_date' in data:
        lpo.expected_delivery_date = data['expected_delivery_date']
    if 'currency' in data and data['currency']:
        lpo.currency = data['currency']
    lpo.save()
    return lpo


def delete_lpo(lpo, user):
    if lpo.status != LocalPurchaseOrder.STATUS_DRAFT:
        raise ValueError('Only draft LPOs may be deleted.')
    if not user.is_job_manager:
        raise PermissionError('Only administrators or supervisors can delete draft LPOs.')
    if user.organization_id and not user.is_superuser and lpo.organization_id != user.organization_id:
        raise PermissionError('You cannot delete this LPO.')
    lpo.delete()


def create_lpo_item(lpo, user, data, defer_refresh=False):
    if lpo.status != LocalPurchaseOrder.STATUS_DRAFT:
        raise ValueError('Line items may only be changed while the LPO is draft.')
    vis = lpos_visible_queryset(user)
    if not vis.filter(pk=lpo.pk).exists():
        raise ValueError('LPO not found or not accessible.')
    product_id = data.get('product_id')
    product = _validate_product_for_lpo(user, product_id, lpo.organization_id)
    qty = Decimal(str(data['quantity']))
    unit_price = Decimal(str(data['unit_price']))
    description = data.get('description') or ''
    if product:
        description = description or product.name
    item = LocalPurchaseOrderItem(
        lpo=lpo,
        product=product,
        description=description,
        quantity=qty,
        unit_price=unit_price,
    )
    item.line_total = _item_line_total(qty, unit_price)
    _sync_item_delivered_from_quantities(item)
    item.full_clean()
    item.save()
    if not defer_refresh:
        refresh_lpo_totals(lpo)
    return item


def update_lpo_item(item, user, data, partial=False, defer_refresh=False):
    lpo = item.lpo
    if lpo.status != LocalPurchaseOrder.STATUS_DRAFT:
        raise ValueError('Line items may only be changed while the LPO is draft.')
    if item.deleted_status:
        raise ValueError('Cannot update a removed line.')
    vis = lpos_visible_queryset(user)
    if not vis.filter(pk=lpo.pk).exists():
        raise ValueError('LPO not found or not accessible.')

    if 'product_id' in data:
        pid = data['product_id']
        item.product = _validate_product_for_lpo(user, pid, lpo.organization_id) if pid else None
    if 'description' in data:
        item.description = data['description'] or ''
    if 'quantity' in data and data['quantity'] is not None:
        item.quantity = Decimal(str(data['quantity']))
    if 'unit_price' in data and data['unit_price'] is not None:
        item.unit_price = Decimal(str(data['unit_price']))

    has_product = item.product_id is not None
    if not has_product and not (item.description and item.description.strip()):
        raise ValueError('Description is required when no product is linked.')

    item.line_total = _item_line_total(item.quantity, item.unit_price)
    _sync_item_delivered_from_quantities(item)
    item.full_clean()
    item.save()
    if not defer_refresh:
        refresh_lpo_totals(lpo)
    return item


def delete_lpo_item(item, user, defer_refresh=False):
    lpo = item.lpo
    if lpo.status != LocalPurchaseOrder.STATUS_DRAFT:
        raise ValueError('Line items may only be deleted while the LPO is draft.')
    vis = lpos_visible_queryset(user)
    if not vis.filter(pk=lpo.pk).exists():
        raise ValueError('LPO not found or not accessible.')
    if item.deleted_status:
        raise ValueError('Line item already removed.')
    item.deleted_status = True
    item.save(update_fields=('deleted_status', 'updated_at'))
    if not defer_refresh:
        refresh_lpo_totals(lpo)


def _partition_patch_line_ops(delete_ids, upserts):
    del_set = {str(u) for u in (delete_ids or [])}
    creates, updates = [], []
    for raw in upserts or []:
        row = dict(raw)
        item_id = row.get('item_id')
        if item_id:
            sid = str(item_id)
            if sid in del_set:
                raise ValueError('Cannot update and delete the same line in one request.')
            updates.append(row)
        else:
            creates.append(row)
    return del_set, creates, updates


def _uniq_ids_preserve(lst):
    out, seen = [], set()
    for x in lst or []:
        s = str(x)
        if s not in seen:
            seen.add(s)
            out.append(x)
    return out


@transaction.atomic
def patch_local_purchase_order(lpo, user, validated_data, partial=True):
    payload = dict(validated_data)
    items_seg = payload.pop('items', None)
    deletes_raw = payload.pop('item_ids_to_delete', None)

    delete_list_unique = _uniq_ids_preserve(deletes_raw if deletes_raw is not None else [])
    upserts = [dict(r) for r in items_seg] if items_seg is not None else None

    has_line_work = bool(
        (upserts and len(upserts) > 0) or (len(delete_list_unique) > 0),
    )

    if has_line_work and lpo.status != LocalPurchaseOrder.STATUS_DRAFT:
        raise ValueError('Line items can only be changed while the LPO is draft.')

    vis = lpos_visible_queryset(user)
    if not vis.filter(pk=lpo.pk).exists():
        raise ValueError('LPO not found or not accessible.')

    del_set, creates, updates = _partition_patch_line_ops(delete_list_unique, upserts or [])
    normalized_creates = [dict(row) for row in creates]
    updates_validated = updates

    update_lpo_header(lpo, user, payload, partial=partial)

    if not has_line_work:
        lpo.refresh_from_db()
        return lpo

    for did in delete_list_unique:
        item = LocalPurchaseOrderItem.objects.filter(lpo=lpo, pk=did).first()
        if not item:
            raise ValueError(f'Line item not found: {did}')
        if item.deleted_status:
            raise ValueError(f'Line item not found or already removed: {did}')
        delete_lpo_item(item, user, defer_refresh=True)

    for u in updates_validated:
        item = LocalPurchaseOrderItem.objects.filter(
            lpo=lpo,
            pk=u['item_id'],
            deleted_status=False,
        ).first()
        if not item:
            raise ValueError(f'Unknown line item: {u["item_id"]}')
        patch = {k: v for k, v in u.items() if k != 'item_id'}
        update_lpo_item(item, user, patch, partial=True, defer_refresh=True)

    for row in normalized_creates:
        create_lpo_item(lpo, user, row, defer_refresh=True)

    refresh_lpo_totals(lpo)
    return lpo


def _sync_receipt_status(lpo):
    """Update header status from active lines' receipt and delivered_status (post-receive)."""
    items = list(active_lpo_items_qs(lpo))
    if not items:
        return lpo
    all_delivered = all(i.delivered_status for i in items)
    any_positive = any(i.quantity_received > 0 for i in items)
    has_strict_partial = any(Decimal('0') < i.quantity_received < i.quantity for i in items)

    if lpo.status in (
        LocalPurchaseOrder.STATUS_ISSUED,
        LocalPurchaseOrder.STATUS_IN_TRANSIT,
        LocalPurchaseOrder.STATUS_PARTIALLY_RECEIVED,
    ):
        if all_delivered:
            lpo.status = LocalPurchaseOrder.STATUS_RECEIVED
            lpo.delivered_at = timezone.now()
            lpo.save(update_fields=('status', 'delivered_at', 'updated_at'))
        elif has_strict_partial or (any_positive and not all_delivered):
            if lpo.status != LocalPurchaseOrder.STATUS_PARTIALLY_RECEIVED:
                lpo.status = LocalPurchaseOrder.STATUS_PARTIALLY_RECEIVED
                lpo.save(update_fields=('status', 'updated_at'))
    return lpo


@transaction.atomic
def receive_lpo_lines(lpo, user, lines_payload):
    """
    lines_payload: list of {'item_id': uuid, 'quantity_received': Decimal or str}
    Sets quantity_received per line to the supplied absolute totals.
    """
    if lpo.status not in (
        LocalPurchaseOrder.STATUS_ISSUED,
        LocalPurchaseOrder.STATUS_IN_TRANSIT,
        LocalPurchaseOrder.STATUS_PARTIALLY_RECEIVED,
    ):
        raise ValueError('Receiving is only allowed for issued or in-progress LPOs.')
    vis = lpos_visible_queryset(user)
    if not vis.filter(pk=lpo.pk).exists():
        raise ValueError('LPO not found or not accessible.')

    if not isinstance(lines_payload, list) or not lines_payload:
        raise ValueError('Non-empty lines list is required.')

    locked = list(
        LocalPurchaseOrderItem.objects.select_for_update()
        .filter(lpo=lpo, deleted_status=False)
        .order_by('created_at', 'id')
    )
    by_id = {str(i.id): i for i in locked}

    for row in lines_payload:
        item_id = str(row.get('item_id') or row.get('id') or '')
        if item_id not in by_id:
            raise ValueError(f'Unknown line item: {item_id}')
        item = by_id[item_id]
        new_recv = Decimal(str(row['quantity_received']))
        if new_recv < 0:
            raise ValueError('quantity_received cannot be negative.')
        if new_recv > item.quantity:
            raise ValueError('quantity_received exceeds ordered quantity for this item.')
        item.quantity_received = new_recv
        _sync_item_delivered_from_quantities(item)
        item.full_clean()
        item.save(update_fields=('quantity_received', 'delivered_status', 'updated_at'))

    lpo.refresh_from_db()
    _sync_receipt_status(lpo)
    return lpo


def transition_lpo_status(lpo, user, new_status):
    """Explicit workflow transitions."""
    vis = lpos_visible_queryset(user)
    if not vis.filter(pk=lpo.pk).exists():
        raise ValueError('LPO not found or not accessible.')

    old = lpo.status
    if old == LocalPurchaseOrder.STATUS_CANCELLED:
        raise ValueError('Cancelled LPOs cannot change status.')
    if old == LocalPurchaseOrder.STATUS_RECEIVED and new_status != LocalPurchaseOrder.STATUS_RECEIVED:
        raise ValueError('Cannot change status after receipt is complete.')

    if new_status == LocalPurchaseOrder.STATUS_ISSUED:
        if old != LocalPurchaseOrder.STATUS_DRAFT:
            raise ValueError('Only draft LPOs can be issued.')
        if not active_lpo_items_qs(lpo).exists():
            raise ValueError('At least one line item is required to issue an LPO.')
        lpo.lpo_number = _next_lpo_number(lpo.organization_id)
        lpo.status = LocalPurchaseOrder.STATUS_ISSUED
        lpo.issued_at = timezone.now()
        lpo.save(update_fields=('lpo_number', 'status', 'issued_at', 'updated_at'))
        return lpo

    if new_status == LocalPurchaseOrder.STATUS_IN_TRANSIT:
        if old != LocalPurchaseOrder.STATUS_ISSUED:
            raise ValueError('Only issued LPOs can move to in transit.')
        lpo.status = LocalPurchaseOrder.STATUS_IN_TRANSIT
        lpo.save(update_fields=('status', 'updated_at'))
        return lpo

    if new_status == LocalPurchaseOrder.STATUS_CANCELLED:
        if old not in (
            LocalPurchaseOrder.STATUS_DRAFT,
            LocalPurchaseOrder.STATUS_ISSUED,
            LocalPurchaseOrder.STATUS_IN_TRANSIT,
        ):
            raise ValueError('This LPO cannot be cancelled in its current state.')
        lpo.status = LocalPurchaseOrder.STATUS_CANCELLED
        lpo.save(update_fields=('status', 'updated_at'))
        return lpo

    if new_status == LocalPurchaseOrder.STATUS_RECEIVED:
        if old not in (
            LocalPurchaseOrder.STATUS_IN_TRANSIT,
            LocalPurchaseOrder.STATUS_PARTIALLY_RECEIVED,
            LocalPurchaseOrder.STATUS_ISSUED,
        ):
            raise ValueError('Invalid transition to received.')
        for item in active_lpo_items_qs(lpo):
            if not item.delivered_status:
                raise ValueError('All lines must be fully delivered before marking received.')
        lpo.status = LocalPurchaseOrder.STATUS_RECEIVED
        lpo.delivered_at = timezone.now()
        lpo.save(update_fields=('status', 'delivered_at', 'updated_at'))
        return lpo

    raise ValueError(f'Transition to {new_status} is not supported via this action.')
