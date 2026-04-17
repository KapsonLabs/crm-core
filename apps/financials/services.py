from decimal import Decimal

from django.db.models import Max, Sum
from django.utils import timezone

from apps.jobs.services import is_job_manager, job_queryset_for_user

from .models import Invoice, InvoicePayment, Requisition


def invoices_for_user(user):
    qs = Invoice.objects.select_related(
        'job', 'job__customer', 'organization', 'created_by',
    ).prefetch_related('payments')
    if is_job_manager(user):
        if user.organization_id:
            return qs.filter(organization_id=user.organization_id)
        return qs
    job_ids = job_queryset_for_user(user).values_list('id', flat=True)
    return qs.filter(job_id__in=job_ids)


def invoice_balance_due(invoice):
    paid = invoice.payments.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    return invoice.total - paid


def _next_invoice_number(organization_id):
    today = timezone.now().date().strftime('%Y%m%d')
    prefix = f'INV-{today}-'
    last = Invoice.objects.filter(
        organization_id=organization_id,
        invoice_number__startswith=prefix,
    ).aggregate(m=Max('invoice_number'))
    max_num = last['m']
    if max_num:
        try:
            n = int(max_num.split('-')[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    else:
        n = 1
    return f'{prefix}{n:04d}'


def create_invoice(user, data):
    from datetime import date

    job_id = data['job_id']
    job = job_queryset_for_user(user).select_related('organization').get(pk=job_id)
    subtotal = Decimal(str(data.get('subtotal', '0.00')))
    tax_amount = Decimal(str(data.get('tax_amount', '0.00')))
    total = Decimal(str(data.get('total', subtotal + tax_amount)))
    currency = data.get('currency', 'USD')
    status = data.get('status', Invoice.STATUS_DRAFT)
    notes = data.get('notes', '')
    issued_at = data.get('issued_at')
    if issued_at is None:
        issued_at = date.today()
    due_at = data.get('due_at')

    return Invoice.objects.create(
        job=job,
        organization=job.organization,
        created_by=user,
        invoice_number=_next_invoice_number(job.organization_id),
        status=status,
        currency=currency,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total,
        issued_at=issued_at,
        due_at=due_at,
        notes=notes,
    )


def update_invoice(instance, user, data, partial=False):
    if not is_job_manager(user):
        raise PermissionError('Only administrators or supervisors can update invoices.')
    if instance.status == Invoice.STATUS_VOID:
        raise ValueError('Cannot edit a void invoice.')
    if data.get('status') == Invoice.STATUS_VOID:
        raise ValueError('Use the invoice void endpoint to void an invoice.')
    for key in ('subtotal', 'tax_amount', 'total', 'currency', 'status', 'issued_at', 'due_at', 'notes'):
        if key not in data:
            continue
        val = data[key]
        if key in ('subtotal', 'tax_amount', 'total') and val is not None:
            val = Decimal(str(val))
        setattr(instance, key, val)
    instance.save()
    _refresh_invoice_payment_status(instance)
    instance.refresh_from_db()
    return instance


def void_invoice(instance, user):
    if not is_job_manager(user):
        raise PermissionError('Only administrators or supervisors can void invoices.')
    instance.status = Invoice.STATUS_VOID
    instance.save(update_fields=['status', 'updated_at'])
    return instance


def _refresh_invoice_payment_status(invoice):
    if invoice.status == Invoice.STATUS_VOID:
        return
    total_paid = invoice.payments.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    if invoice.total <= 0:
        return
    if total_paid >= invoice.total:
        invoice.status = Invoice.STATUS_PAID
    elif total_paid > 0:
        invoice.status = Invoice.STATUS_PARTIALLY_PAID
    elif invoice.status in (Invoice.STATUS_PAID, Invoice.STATUS_PARTIALLY_PAID):
        invoice.status = Invoice.STATUS_SENT
    invoice.save(update_fields=['status', 'updated_at'])


def record_payment(user, data):
    invoice_id = data['invoice_id']
    invoice = Invoice.objects.select_related('organization').get(pk=invoice_id)
    if not invoices_for_user(user).filter(pk=invoice.pk).exists():
        raise PermissionError('Invoice not found or not accessible.')
    if invoice.status == Invoice.STATUS_VOID:
        raise ValueError('Cannot record payment on a void invoice.')
    amount = Decimal(str(data['amount']))
    if amount <= 0:
        raise ValueError('Amount must be positive.')
    paid_at = data['paid_at']
    method = data.get('method', InvoicePayment.METHOD_OTHER)
    reference = data.get('reference', '')
    pay = InvoicePayment.objects.create(
        invoice=invoice,
        amount=amount,
        paid_at=paid_at,
        method=method,
        reference=reference,
        recorded_by=user,
    )
    _refresh_invoice_payment_status(invoice)
    invoice.refresh_from_db()
    return pay


def record_payment_for_invoice(invoice, user, data):
    payload = {
        'invoice_id': invoice.id,
        'amount': data['amount'],
        'paid_at': data['paid_at'],
        'method': data.get('method', InvoicePayment.METHOD_OTHER),
        'reference': data.get('reference', ''),
    }
    return record_payment(user, payload)


def delete_payment(payment, user):
    if not is_job_manager(user):
        raise PermissionError('Only administrators or supervisors can delete payments.')
    invoice = payment.invoice
    if not invoices_for_user(user).filter(pk=invoice.pk).exists():
        raise PermissionError('Not accessible.')
    payment.delete()
    _refresh_invoice_payment_status(invoice)
    invoice.refresh_from_db()


def requisitions_for_user(user):
    qs = Requisition.objects.select_related('organization', 'requested_by', 'job')
    if is_job_manager(user):
        if user.organization_id:
            return qs.filter(organization_id=user.organization_id)
        return qs
    return qs.filter(requested_by=user)


def create_requisition(user, data):
    from apps.organization.models import Organization

    org_id = data.get('organization_id')
    if user.is_superuser and org_id:
        organization = Organization.objects.get(pk=org_id)
    elif user.organization_id:
        organization = Organization.objects.get(pk=user.organization_id)
    else:
        raise ValueError('Your account must belong to an organization.')

    job_id = data.get('job_id')
    job = None
    if job_id:
        job = job_queryset_for_user(user).get(pk=job_id)
        if job.organization_id != organization.id:
            raise ValueError('Job must belong to the same organization.')

    return Requisition.objects.create(
        organization=organization,
        requested_by=user,
        job=job,
        title=data['title'],
        description=data.get('description', ''),
        amount=Decimal(str(data.get('amount', '0.00'))),
        currency=data.get('currency', 'USD'),
        status=data.get('status', Requisition.STATUS_DRAFT),
    )


def update_requisition(instance, user, data, partial=False):
    if not is_job_manager(user) and instance.requested_by_id != user.id:
        raise PermissionError('You can only edit your own requisitions.')
    if 'job_id' in data:
        jid = data['job_id']
        if jid:
            job = job_queryset_for_user(user).get(pk=jid)
            if job.organization_id != instance.organization_id:
                raise ValueError('Job must belong to the same organization.')
            instance.job = job
        else:
            instance.job = None
    for key in ('title', 'description', 'amount', 'currency', 'status', 'submitted_at', 'resolved_at'):
        if key not in data:
            continue
        val = data[key]
        if key == 'amount' and val is not None:
            val = Decimal(str(val))
        setattr(instance, key, val)
    instance.save()
    return instance


def delete_requisition(instance, user):
    if not is_job_manager(user) and instance.requested_by_id != user.id:
        raise PermissionError('You can only delete your own requisitions.')
    if not is_job_manager(user) and instance.status != Requisition.STATUS_DRAFT:
        raise PermissionError('You can only delete draft requisitions.')
    instance.delete()
