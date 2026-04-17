from django.contrib import admin

from .models import Invoice, InvoicePayment, Requisition


class InvoicePaymentInline(admin.TabularInline):
    model = InvoicePayment
    extra = 0
    raw_id_fields = ('recorded_by',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'job', 'organization', 'status', 'total', 'issued_at')
    list_filter = ('status', 'organization')
    search_fields = ('invoice_number', 'notes')
    raw_id_fields = ('job', 'organization', 'created_by')
    inlines = [InvoicePaymentInline]


@admin.register(InvoicePayment)
class InvoicePaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'paid_at', 'method')
    raw_id_fields = ('invoice', 'recorded_by')


@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'requested_by', 'status', 'amount')
    list_filter = ('status', 'organization')
    raw_id_fields = ('organization', 'requested_by', 'job')
