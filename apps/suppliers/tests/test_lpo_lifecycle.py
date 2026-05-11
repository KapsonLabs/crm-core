from decimal import Decimal
import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.organization.models import Branch, Organization
from apps.suppliers.models import LocalPurchaseOrder, LocalPurchaseOrderItem

class SuppliersLPOLifecycleTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Suppliers Org')
        cls.branch = Branch.objects.create(organization=cls.org, name='Main', code='supm')
        cls.user = User.objects.create_user(
            email='procure@example.com',
            username='procure',
            password='testpass123',
            is_staff=True,
            organization=cls.org,
            branch=cls.branch,
        )
        cls.restricted = User.objects.create_user(
            email='staffnobranch@example.com',
            username='staffnobranch',
            password='testpass123',
            is_staff=False,
            organization=cls.org,
        )

    def setUp(self):
        self.client.force_authenticate(self.user)

    def _create_supplier(self):
        r = self.client.post(
            reverse('suppliers:supplier-list-create'),
            {
                'name': 'Ace Parts',
                'branch_id': str(self.branch.id),
                'phone_number': '+256700000001',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data['data']['id']

    def test_lpo_creation_issue_receive_and_completion(self):
        sid = self._create_supplier()
        r = self.client.post(
            reverse('suppliers:lpo-list-create'),
            {
                'supplier_id': sid,
                'branch_id': str(self.branch.id),
                'currency': 'UGX',
                'items': [
                    {'description': 'Widget A', 'quantity': '10', 'unit_price': '5.00'},
                ],
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        lpo_id = r.data['data']['id']
        self.assertEqual(r.data['data']['status'], LocalPurchaseOrder.STATUS_DRAFT)
        self.assertEqual(len(r.data['data']['items']), 1)
        self.assertEqual(Decimal(r.data['data']['subtotal']), Decimal('50.00'))

        item_id = r.data['data']['items'][0]['id']
        self.assertEqual(Decimal(r.data['data']['items'][0]['line_total']), Decimal('50.00'))

        r = self.client.post(
            reverse('suppliers:lpo-transition', kwargs={'pk': lpo_id}),
            {'status': LocalPurchaseOrder.STATUS_ISSUED},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['data']['status'], LocalPurchaseOrder.STATUS_ISSUED)
        self.assertTrue(r.data['data']['lpo_number'])

        r = self.client.post(
            reverse('suppliers:lpo-transition', kwargs={'pk': lpo_id}),
            {'status': LocalPurchaseOrder.STATUS_IN_TRANSIT},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

        r = self.client.post(
            reverse('suppliers:lpo-receive', kwargs={'pk': lpo_id}),
            {'lines': [{'item_id': item_id, 'quantity_received': '4'}]},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['data']['status'], LocalPurchaseOrder.STATUS_PARTIALLY_RECEIVED)
        self.assertFalse(r.data['data']['items'][0]['delivered_status'])

        r = self.client.post(
            reverse('suppliers:lpo-receive', kwargs={'pk': lpo_id}),
            {'lines': [{'item_id': item_id, 'quantity_received': '10'}]},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['data']['status'], LocalPurchaseOrder.STATUS_RECEIVED)
        self.assertIsNotNone(r.data['data']['delivered_at'])
        self.assertTrue(r.data['data']['items'][0]['delivered_status'])

    def test_cannot_edit_lines_after_issue(self):
        sid = self._create_supplier()
        r = self.client.post(
            reverse('suppliers:lpo-list-create'),
            {
                'supplier_id': sid,
                'items': [
                    {'description': 'X', 'quantity': '1', 'unit_price': '1'},
                ],
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        lpo_id = r.data['data']['id']
        item_id = r.data['data']['items'][0]['id']

        self.client.post(
            reverse('suppliers:lpo-transition', kwargs={'pk': lpo_id}),
            {'status': LocalPurchaseOrder.STATUS_ISSUED},
            format='json',
        )
        r = self.client.patch(
            reverse(
                'suppliers:lpo-item-detail',
                kwargs={'lpo_pk': lpo_id, 'pk': item_id},
            ),
            {'quantity': '2'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, r.data)
        self.assertIn('message', r.data)

    def test_restricted_user_cannot_delete_draft_lpo(self):
        sid = self._create_supplier()
        r = self.client.post(
            reverse('suppliers:lpo-list-create'),
            {
                'supplier_id': sid,
                'items': [
                    {'description': 'Y', 'quantity': '1', 'unit_price': '1'},
                ],
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        lpo_id = r.data['data']['id']
        self.client.force_authenticate(self.restricted)
        r = self.client.delete(reverse('suppliers:lpo-detail', kwargs={'pk': lpo_id}))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, r.data)

    def test_lpo_create_requires_items(self):
        sid = self._create_supplier()
        r = self.client.post(
            reverse('suppliers:lpo-list-create'),
            {'supplier_id': sid},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, r.data)
        self.assertIn('items', r.data)

    def test_lpo_create_accepts_multiple_items(self):
        sid = self._create_supplier()
        r = self.client.post(
            reverse('suppliers:lpo-list-create'),
            {
                'supplier_id': sid,
                'items': [
                    {'description': 'A', 'quantity': '1', 'unit_price': '1'},
                    {'description': 'B', 'quantity': '1', 'unit_price': '1'},
                ],
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(len(r.data['data']['items']), 2)

    def test_patch_draft_updates_deletes_and_adds_lines(self):
        sid = self._create_supplier()
        r = self.client.post(
            reverse('suppliers:lpo-list-create'),
            {
                'supplier_id': sid,
                'items': [
                    {'description': 'Keep', 'quantity': '2', 'unit_price': '1.00'},
                    {'description': 'RemoveMe', 'quantity': '1', 'unit_price': '10.00'},
                ],
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        lpo_id = r.data['data']['id']
        items = sorted(r.data['data']['items'], key=lambda x: x['description'])
        i_keep = next(x for x in items if x['description'] == 'Keep')
        i_remove = next(x for x in items if x['description'] == 'RemoveMe')

        r = self.client.patch(
            reverse('suppliers:lpo-detail', kwargs={'pk': lpo_id}),
            {
                'notes': 'patched-notes',
                'item_ids_to_delete': [str(i_remove['id'])],
                'items': [
                    {'item_id': str(i_keep['id']), 'quantity': '5'},
                    {'description': 'NewLine', 'quantity': '2', 'unit_price': '3.00'},
                ],
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['data']['notes'], 'patched-notes')
        descs = {x['description'] for x in r.data['data']['items']}
        self.assertEqual(descs, {'Keep', 'NewLine'})
        removed_db = LocalPurchaseOrderItem.objects.get(pk=i_remove['id'])
        self.assertTrue(removed_db.deleted_status)
        # 5 * 1 + 2 * 3 = 11
        self.assertEqual(Decimal(r.data['data']['subtotal']), Decimal('11.00'))

    def test_patch_issued_with_line_payload_rejected(self):
        sid = self._create_supplier()
        r = self.client.post(
            reverse('suppliers:lpo-list-create'),
            {
                'supplier_id': sid,
                'items': [
                    {'description': 'Only', 'quantity': '1', 'unit_price': '1'},
                ],
            },
            format='json',
        )
        lpo_id = r.data['data']['id']
        item_id = r.data['data']['items'][0]['id']
        self.client.post(
            reverse('suppliers:lpo-transition', kwargs={'pk': lpo_id}),
            {'status': LocalPurchaseOrder.STATUS_ISSUED},
            format='json',
        )
        r = self.client.patch(
            reverse('suppliers:lpo-detail', kwargs={'pk': lpo_id}),
            {'items': [{'item_id': str(item_id), 'quantity': '9'}]},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, r.data)
        self.assertIn('message', r.data)

        r_ok = self.client.patch(
            reverse('suppliers:lpo-detail', kwargs={'pk': lpo_id}),
            {'notes': 'after issue ok'},
            format='json',
        )
        self.assertEqual(r_ok.status_code, status.HTTP_200_OK, r_ok.data)
        self.assertEqual(r_ok.data['data']['notes'], 'after issue ok')

    def test_patch_unknown_line_delete_id_returns_400(self):
        sid = self._create_supplier()
        r = self.client.post(
            reverse('suppliers:lpo-list-create'),
            {
                'supplier_id': sid,
                'items': [
                    {'description': 'Only', 'quantity': '1', 'unit_price': '1'},
                ],
            },
            format='json',
        )
        lpo_id = r.data['data']['id']
        r = self.client.patch(
            reverse('suppliers:lpo-detail', kwargs={'pk': lpo_id}),
            {'item_ids_to_delete': [str(uuid.uuid4())]},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, r.data)
        self.assertIn('message', r.data)

    def test_patch_unknown_line_update_id_returns_400(self):
        sid = self._create_supplier()
        r = self.client.post(
            reverse('suppliers:lpo-list-create'),
            {
                'supplier_id': sid,
                'items': [
                    {'description': 'Only', 'quantity': '1', 'unit_price': '1'},
                ],
            },
            format='json',
        )
        lpo_id = r.data['data']['id']
        r = self.client.patch(
            reverse('suppliers:lpo-detail', kwargs={'pk': lpo_id}),
            {'items': [{'item_id': str(uuid.uuid4()), 'quantity': '2'}]},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, r.data)
        self.assertIn('message', r.data)

    def test_issue_and_receive_ignore_soft_deleted_lines(self):
        sid = self._create_supplier()
        r = self.client.post(
            reverse('suppliers:lpo-list-create'),
            {
                'supplier_id': sid,
                'items': [
                    {'description': 'ActiveLine', 'quantity': '10', 'unit_price': '1'},
                    {'description': 'GoneSoon', 'quantity': '1', 'unit_price': '99'},
                ],
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        lpo_id = r.data['data']['id']
        items_by_desc = {x['description']: x for x in r.data['data']['items']}
        gone_id = items_by_desc['GoneSoon']['id']
        active_id = items_by_desc['ActiveLine']['id']

        r = self.client.patch(
            reverse('suppliers:lpo-detail', kwargs={'pk': lpo_id}),
            {'item_ids_to_delete': [str(gone_id)]},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertTrue(LocalPurchaseOrderItem.objects.get(pk=gone_id).deleted_status)

        r = self.client.post(
            reverse('suppliers:lpo-transition', kwargs={'pk': lpo_id}),
            {'status': LocalPurchaseOrder.STATUS_ISSUED},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        r = self.client.post(
            reverse('suppliers:lpo-transition', kwargs={'pk': lpo_id}),
            {'status': LocalPurchaseOrder.STATUS_IN_TRANSIT},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

        r = self.client.post(
            reverse('suppliers:lpo-receive', kwargs={'pk': lpo_id}),
            {'lines': [{'item_id': active_id, 'quantity_received': '10'}]},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['data']['status'], LocalPurchaseOrder.STATUS_RECEIVED)
        payload_item = r.data['data']['items'][0]
        self.assertEqual(payload_item['id'], active_id)
        self.assertTrue(payload_item['delivered_status'])

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name='Del Org')
        cls.branch = Branch.objects.create(organization=cls.org, name='B', code='bdel')
        cls.user = User.objects.create_user(
            email='mj@example.com',
            username='mj',
            password='x',
            is_staff=True,
            organization=cls.org,
            branch=cls.branch,
        )

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_cannot_delete_supplier_with_lpo(self):
        r = self.client.post(
            reverse('suppliers:supplier-list-create'),
            {'name': 'S', 'branch_id': str(self.branch.id)},
            format='json',
        )
        sid = r.data['data']['id']
        self.client.post(
            reverse('suppliers:lpo-list-create'),
            {
                'supplier_id': sid,
                'items': [
                    {'description': 'Z', 'quantity': '1', 'unit_price': '1'},
                ],
            },
            format='json',
        )
        r = self.client.delete(reverse('suppliers:supplier-detail', kwargs={'pk': sid}))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('message', r.data)
