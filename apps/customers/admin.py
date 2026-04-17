from django.contrib import admin

from .models import Customer, CustomerFeedback


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'organization', 'phone_number', 'email', 'is_active')
    list_filter = ('is_active', 'organization')
    search_fields = ('first_name', 'last_name', 'email', 'phone_number')


@admin.register(CustomerFeedback)
class CustomerFeedbackAdmin(admin.ModelAdmin):
    list_display = ('subject', 'customer', 'submitted_by', 'rating', 'created_at')
    search_fields = ('subject', 'body')
    raw_id_fields = ('customer', 'submitted_by')
