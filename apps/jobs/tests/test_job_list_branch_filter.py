from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.jobs.models import Job, Product
from apps.organization.models import Branch, Organization


class JobListBranchFilterTests(APITestCase):
    """GET /api/jobs/list/?branch_id= filters jobs by branch."""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Jobs Test Org')
        cls.branch_a = Branch.objects.create(
            organization=cls.org, name='Branch A', code='ja',
        )
        cls.branch_b = Branch.objects.create(
            organization=cls.org, name='Branch B', code='jb',
        )
        cls.user = User.objects.create_user(
            email='manager@example.com',
            username='manager',
            password='testpass123',
            is_staff=True,
            organization=cls.org,
        )
        cls.cust_a = Customer.objects.create(
            organization=cls.org,
            branch=cls.branch_a,
            first_name='A',
            last_name='One',
            phone_number='+1000000001',
        )
        cls.cust_b = Customer.objects.create(
            organization=cls.org,
            branch=cls.branch_b,
            first_name='B',
            last_name='Two',
            phone_number='+1000000002',
        )
        cls.job_a = Job.objects.create(
            customer=cls.cust_a,
            organization=cls.org,
            branch=cls.branch_a,
            created_by=cls.user,
            title='Job on A',
        )
        cls.job_b = Job.objects.create(
            customer=cls.cust_b,
            organization=cls.org,
            branch=cls.branch_b,
            created_by=cls.user,
            title='Job on B',
        )

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_list_without_branch_returns_all_visible(self):
        url = reverse('jobs:job-list-create')
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {j['id'] for j in r.data['data']}
        self.assertEqual(ids, {str(self.job_a.id), str(self.job_b.id)})

    def test_list_with_branch_id_filters(self):
        url = reverse('jobs:job-list-create')
        r = self.client.get(url, {'branch_id': str(self.branch_a.id)})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [j['id'] for j in r.data['data']]
        self.assertEqual(ids, [str(self.job_a.id)])


class JobCreateAndListIntegrationTests(APITestCase):
    """POST create job then GET list with branch_id returns the new job."""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Integration Org')
        cls.branch = Branch.objects.create(
            organization=cls.org, name='Main', code='main',
        )
        cls.user = User.objects.create_user(
            email='sup@example.com',
            username='sup',
            password='testpass123',
            is_staff=True,
            organization=cls.org,
        )
        cls.customer = Customer.objects.create(
            organization=cls.org,
            branch=cls.branch,
            first_name='Jane',
            last_name='Doe',
            phone_number='+256700000000',
            email='jane@example.com',
        )
        cls.product = Product.objects.create(
            organization=cls.org,
            branch=cls.branch,
            kind=Product.KIND_PRODUCT,
            name='Air Filter',
            price=Decimal('10000.00'),
        )

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_post_then_get_list_by_branch(self):
        url = reverse('jobs:job-list-create')
        payload = {
            'customer_id': str(self.customer.id),
            'title': 'Install office network',
            'description': 'Set up switches',
            'branch_id': str(self.branch.id),
            'job_products': [
                {
                    'product_id': str(self.product.id),
                    'quantity': '2',
                    'unit_price': '10000',
                },
            ],
        }
        r = self.client.post(url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        job_id = r.data['data']['id']

        r2 = self.client.get(url, {'branch_id': str(self.branch.id)})
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        ids = [j['id'] for j in r2.data['data']]
        self.assertIn(job_id, ids)
