# Generated manually for Django migration tooling parity.

import uuid
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('financials', '0004_alter_invoicepayment_method_and_more'),
        ('jobs', '0003_job_phone_number'),
        ('organization', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('contact_name', models.CharField(blank=True, max_length=255)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('phone_number', models.CharField(blank=True, max_length=30)),
                ('physical_address', models.CharField(blank=True, max_length=500)),
                ('tax_id', models.CharField(blank=True, max_length=100)),
                ('payment_terms', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'branch',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='suppliers',
                        to='organization.branch',
                    ),
                ),
                (
                    'organization',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='suppliers',
                        to='organization.organization',
                    ),
                ),
            ],
            options={
                'db_table': 'suppliers_supplier',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='LocalPurchaseOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('lpo_number', models.CharField(blank=True, max_length=64, null=True)),
                ('currency', models.CharField(default='UGX', max_length=10)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('draft', 'Draft'),
                            ('issued', 'Issued'),
                            ('in_transit', 'In transit'),
                            ('partially_received', 'Partially received'),
                            ('received', 'Received'),
                            ('cancelled', 'Cancelled'),
                        ],
                        default='draft',
                        max_length=30,
                    ),
                ),
                ('subtotal', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('notes', models.TextField(blank=True)),
                ('expected_delivery_date', models.DateField(blank=True, null=True)),
                ('issued_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'approved_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='local_purchase_orders_approved',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'branch',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='local_purchase_orders',
                        to='organization.branch',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='local_purchase_orders_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'organization',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='local_purchase_orders',
                        to='organization.organization',
                    ),
                ),
                (
                    'supplier',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='local_purchase_orders',
                        to='suppliers.supplier',
                    ),
                ),
                (
                    'job',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='local_purchase_orders',
                        to='jobs.job',
                    ),
                ),
                (
                    'requisition',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='local_purchase_orders',
                        to='financials.requisition',
                    ),
                ),
            ],
            options={
                'db_table': 'suppliers_local_purchase_order',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LocalPurchaseOrderItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('line_number', models.PositiveIntegerField(default=1)),
                ('description', models.CharField(blank=True, max_length=512)),
                ('quantity', models.DecimalField(decimal_places=4, default=Decimal('1'), max_digits=14)),
                ('quantity_received', models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=14)),
                ('unit_price', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('line_total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'lpo',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='items',
                        to='suppliers.localpurchaseorder',
                    ),
                ),
                (
                    'product',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='lpo_lines',
                        to='jobs.product',
                    ),
                ),
            ],
            options={
                'db_table': 'suppliers_local_purchase_order_item',
                'ordering': ['lpo', 'line_number', 'created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='supplier',
            index=models.Index(fields=['organization', 'is_active'], name='suppliers_s_organiz_6f_idx'),
        ),
        migrations.AddIndex(
            model_name='supplier',
            index=models.Index(fields=['branch', 'name'], name='suppliers_s_branch__idx'),
        ),
        migrations.AddIndex(
            model_name='localpurchaseorder',
            index=models.Index(fields=['organization', 'status'], name='suppliers_l_org_stat_idx'),
        ),
        migrations.AddIndex(
            model_name='localpurchaseorder',
            index=models.Index(fields=['branch', 'status'], name='suppliers_l_branch_stat_idx'),
        ),
        migrations.AddIndex(
            model_name='localpurchaseorder',
            index=models.Index(fields=['supplier', 'status'], name='suppliers_l_supp_stat_idx'),
        ),
        migrations.AddIndex(
            model_name='localpurchaseorderitem',
            index=models.Index(fields=['lpo', 'line_number'], name='suppliers_li_lpo_line_idx'),
        ),
        migrations.AddConstraint(
            model_name='localpurchaseorder',
            constraint=models.UniqueConstraint(
                condition=models.Q(lpo_number__isnull=False),
                fields=('organization', 'lpo_number'),
                name='suppliers_lpo_org_number_uniq_when_set',
            ),
        ),
        migrations.AddConstraint(
            model_name='localpurchaseorderitem',
            constraint=models.UniqueConstraint(
                fields=('lpo', 'line_number'),
                name='suppliers_lpo_line_number_uniq',
            ),
        ),
    ]
