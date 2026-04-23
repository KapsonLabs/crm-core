from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.financials.models import Invoice
from apps.jobs.models import Job
from apps.organization.models import Branch, Organization


class InvoicePaymentCreateBodyTests(APITestCase):
    """POST /api/financials/payments/ with invoice_id in JSON body."""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Fin Test Org')
        cls.branch = Branch.objects.create(organization=cls.org, name='Main', code='fmain')
        cls.user = User.objects.create_user(
            email='finmgr@example.com',
            username='finmgr',
            password='testpass123',
            is_staff=True,
            organization=cls.org,
        )
        cls.customer = Customer.objects.create(
            organization=cls.org,
            branch=cls.branch,
            first_name='C',
            last_name='C',
            phone_number='+2000000000',
        )
        cls.job = Job.objects.create(
            customer=cls.customer,
            organization=cls.org,
            branch=cls.branch,
            created_by=cls.user,
            title='Payable job',
        )
        cls.invoice = Invoice.objects.create(
            job=cls.job,
            organization=cls.org,
            branch=cls.branch,
            created_by=cls.user,
            invoice_number='INV-PLAN-0001',
            status=Invoice.STATUS_SENT,
            currency='UGX',
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0.00'),
            total=Decimal('100.00'),
            issued_at=date.today(),
        )

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_post_payment_with_invoice_id_in_body(self):
        url = reverse('financials:invoice-payment-list-create')
        payload = {
            'invoice_id': str(self.invoice.id),
            'amount': '50.00',
            'paid_at': '2024-06-01T12:00:00Z',
            'method': 'cash',
            'reference': 'REF1',
        }
        r = self.client.post(url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['data']['amount'], '50.00')
        self.assertEqual(r.data['data']['method'], 'cash')
        self.assertIn('invoice', r.data)
        self.assertEqual(r.data['invoice']['id'], str(self.invoice.id))

    def test_post_requires_invoice_id(self):
        url = reverse('financials:invoice-payment-list-create')
        payload = {
            'amount': '10.00',
            'paid_at': '2024-06-01T12:00:00Z',
        }
        r = self.client.post(url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('invoice_id', r.data)

    def test_post_unknown_invoice_404(self):
        other_org = Organization.objects.create(name='Other Org')
        other_branch = Branch.objects.create(organization=other_org, name='O', code='o')
        other_cust = Customer.objects.create(
            organization=other_org,
            branch=other_branch,
            first_name='O',
            last_name='O',
            phone_number='+1999999999',
        )
        other_user = User.objects.create_user(
            email='other@example.com',
            username='otheru',
            password='testpass123',
            is_staff=True,
            organization=other_org,
        )
        other_job = Job.objects.create(
            customer=other_cust,
            organization=other_org,
            branch=other_branch,
            created_by=other_user,
            title='Other',
        )
        other_inv = Invoice.objects.create(
            job=other_job,
            organization=other_org,
            branch=other_branch,
            created_by=other_user,
            invoice_number='INV-OTHER-0001',
            status=Invoice.STATUS_SENT,
            subtotal=Decimal('10.00'),
            tax_amount=Decimal('0.00'),
            total=Decimal('10.00'),
            issued_at=date.today(),
        )
        url = reverse('financials:invoice-payment-list-create')
        payload = {
            'invoice_id': str(other_inv.id),
            'amount': '5.00',
            'paid_at': '2024-06-01T12:00:00Z',
        }
        r = self.client.post(url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
