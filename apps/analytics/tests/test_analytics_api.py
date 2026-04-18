from datetime import date, datetime, timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.financials.models import Invoice, Requisition
from apps.jobs.models import Job, JobAssignment, JobProduct, Product
from apps.organization.models import Branch, Organization


class AnalyticsEndpointsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.year = timezone.now().date().year
        cls.org = Organization.objects.create(name='Analytics Org')
        cls.branch = Branch.objects.create(
            organization=cls.org,
            name='HQ',
            code='hq',
        )
        cls.user = User.objects.create_user(
            email='analytics-mgr@example.com',
            username='analytics-mgr',
            password='testpass123',
            is_staff=True,
            organization=cls.org,
        )
        cls.customer = Customer.objects.create(
            organization=cls.org,
            branch=cls.branch,
            first_name='C',
            last_name='One',
            phone_number='+1000000000',
        )
        cls.job = Job.objects.create(
            customer=cls.customer,
            organization=cls.org,
            branch=cls.branch,
            created_by=cls.user,
            title='Service job',
        )
        Job.objects.filter(pk=cls.job.pk).update(
            created_at=timezone.make_aware(datetime(cls.year, 3, 1, 10, 0, 0)),
        )
        cls.product = Product.objects.create(
            organization=cls.org,
            branch=cls.branch,
            kind=Product.KIND_PRODUCT,
            name='Widget',
            price=Decimal('10.00'),
        )
        cls.service = Product.objects.create(
            organization=cls.org,
            branch=cls.branch,
            kind=Product.KIND_SERVICE,
            name='Install',
            price=Decimal('50.00'),
        )
        cls.inv = Invoice.objects.create(
            job=cls.job,
            organization=cls.org,
            branch=cls.branch,
            invoice_number='INV-TEST-0001',
            status=Invoice.STATUS_SENT,
            total=Decimal('100.00'),
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0.00'),
            issued_at=date(cls.year, 6, 15),
            created_by=cls.user,
        )
        JobProduct.objects.create(
            job=cls.job,
            product=cls.product,
            quantity=Decimal('2'),
            unit_price=Decimal('10.00'),
            line_total=Decimal('20.00'),
        )
        JobProduct.objects.create(
            job=cls.job,
            product=cls.service,
            quantity=Decimal('1'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
        )
        Requisition.objects.create(
            organization=cls.org,
            branch=cls.branch,
            requested_by=cls.user,
            job=cls.job,
            title='Supplies',
            amount=Decimal('25.00'),
            status=Requisition.STATUS_FULFILLED,
            resolved_at=timezone.make_aware(datetime(cls.year, 6, 10, 12, 0, 0)),
        )
        assigned = timezone.now() - timedelta(days=2)
        JobAssignment.objects.create(
            job=cls.job,
            user=cls.user,
            assigned_by=cls.user,
            assigned_at=assigned,
        )
        cls.job.completed_at = timezone.now() - timedelta(days=1)
        cls.job.save(update_fields=['completed_at'])

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_totals(self):
        url = reverse('analytics:analytics-totals')
        r = self.client.get(
            url,
            {'organization_id': str(self.org.id), 'year': str(self.year)},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        d = r.data['data']
        self.assertEqual(d['total_jobs'], 1)
        self.assertEqual(d['revenue'], '100.00')
        self.assertEqual(d['expenditure'], '25.00')
        self.assertEqual(d['profit'], '75.00')

    def test_monthly(self):
        url = reverse('analytics:analytics-monthly')
        r = self.client.get(
            url,
            {'organization_id': str(self.org.id), 'year': str(self.year)},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        months = r.data['data']['months']
        june = next(m for m in months if m['month'] == 6)
        self.assertEqual(june['revenue'], '100.00')
        self.assertEqual(june['expenditure'], '25.00')

    def test_top_selling(self):
        url = reverse('analytics:analytics-top-selling')
        r = self.client.get(
            url,
            {'organization_id': str(self.org.id), 'year': str(self.year)},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.data['data']
        self.assertEqual(len(data['products']), 1)
        self.assertEqual(len(data['services']), 1)
        self.assertEqual(data['products'][0]['total_revenue'], '20.00')
        self.assertEqual(data['services'][0]['total_revenue'], '50.00')

    def test_average_time(self):
        url = reverse('analytics:analytics-avg-time')
        r = self.client.get(
            url,
            {'organization_id': str(self.org.id), 'year': str(self.year)},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        d = r.data['data']
        self.assertEqual(d['sample_size'], 1)
        self.assertGreater(d['average_seconds'], 0)
