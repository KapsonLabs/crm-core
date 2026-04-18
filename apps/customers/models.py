import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='customers',
    )
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='customers',
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customers_customer'
        ordering = ['last_name', 'first_name']
        verbose_name = _('customer')
        verbose_name_plural = _('customers')
        indexes = [
            models.Index(fields=['organization', 'last_name', 'first_name']),
            models.Index(fields=['branch', 'last_name', 'first_name']),
        ]

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class CustomerFeedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='feedback',
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_feedback_submitted',
    )
    subject = models.CharField(max_length=255)
    body = models.TextField()
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customers_customer_feedback'
        ordering = ['-created_at']
        verbose_name = _('customer feedback')
        verbose_name_plural = _('customer feedback')

    def __str__(self):
        return self.subject
