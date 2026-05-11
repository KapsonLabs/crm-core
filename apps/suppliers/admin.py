from django.contrib import admin

from .models import LocalPurchaseOrder, LocalPurchaseOrderItem, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'branch', 'phone_number', 'email', 'is_active')
    list_filter = ('is_active', 'organization')
    search_fields = ('name', 'contact_name', 'email', 'phone_number', 'tax_id')


class LocalPurchaseOrderItemInline(admin.TabularInline):
    model = LocalPurchaseOrderItem
    extra = 0
    readonly_fields = ('line_total', 'deleted_status', 'delivered_status')


@admin.register(LocalPurchaseOrder)
class LocalPurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('lpo_number', 'supplier', 'organization', 'status', 'currency', 'total', 'created_at')
    list_filter = ('status', 'organization')
    search_fields = ('lpo_number', 'notes')
    readonly_fields = ('subtotal', 'total', 'issued_at', 'delivered_at', 'created_at', 'updated_at')
    inlines = [LocalPurchaseOrderItemInline]


@admin.register(LocalPurchaseOrderItem)
class LocalPurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'lpo',
        'description',
        'quantity',
        'quantity_received',
        'delivered_status',
        'deleted_status',
        'unit_price',
        'line_total',
    )
    list_filter = ('deleted_status', 'delivered_status', 'lpo__status')
    search_fields = ('description', 'lpo__lpo_number')
    raw_id_fields = ('lpo', 'product')
