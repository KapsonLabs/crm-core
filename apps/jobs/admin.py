from django.contrib import admin

from .models import Job, JobAssignment, JobProduct, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'organization', 'price', 'is_active', 'created_at')
    list_filter = ('kind', 'is_active', 'organization')
    search_fields = ('name', 'description')


class JobProductInline(admin.TabularInline):
    model = JobProduct
    extra = 0
    raw_id_fields = ('product',)


class JobAssignmentInline(admin.TabularInline):
    model = JobAssignment
    extra = 0
    raw_id_fields = ('user', 'assigned_by')


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'customer', 'status', 'organization', 'created_by', 'created_at')
    list_filter = ('status', 'organization')
    search_fields = ('title', 'description')
    raw_id_fields = ('customer', 'created_by', 'completed_by', 'closed_by', 'branch')
    inlines = [JobProductInline, JobAssignmentInline]


@admin.register(JobAssignment)
class JobAssignmentAdmin(admin.ModelAdmin):
    list_display = ('job', 'user', 'assigned_by', 'assigned_at')
    raw_id_fields = ('job', 'user', 'assigned_by')


@admin.register(JobProduct)
class JobProductAdmin(admin.ModelAdmin):
    list_display = ('job', 'product', 'quantity', 'unit_price', 'line_total')
    raw_id_fields = ('job', 'product')
