from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID

from django.test import TestCase

from apps.accounts.models import User
from apps.organization.models import Branch, Organization


def _make_mock_account(account_id="00000000-0000-0000-0000-000000000001"):
    account = MagicMock()
    account.id = UUID(account_id)
    account.code = "TEST"
    return account


def _make_mock_journal():
    journal = MagicMock()
    journal.id = "00000000-0000-0000-0000-000000000099"
    journal.status = "posted"
    return journal


class SupplierSubledgerCreationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Supplier Test Org")
        cls.branch = Branch.objects.create(organization=cls.org, name="Main", code="supmain")
        cls.user = User.objects.create_user(
            email="sup@example.com",
            username="supuser",
            password="testpass123",
            is_staff=True,
            organization=cls.org,
            branch=cls.branch,
        )

    @patch("apps.suppliers.services.supplier_accounting_service.create_default_entity_accounts")
    def test_create_supplier_creates_ap_subledger(self, mock_create):
        mock_create.return_value = [MagicMock()]
        from apps.suppliers.services import create_supplier

        supplier = create_supplier(
            self.user,
            {
                "branch_id": str(self.branch.id),
                "name": "Acme Supplies",
                "contact_name": "John",
                "phone_number": "+256700000000",
            },
        )
        self.assertIsNotNone(supplier.id)
        mock_create.assert_called_once()
        request = mock_create.call_args.kwargs["request"]
        self.assertEqual(request.entity_type, "supplier")
        self.assertEqual(request.entity_id, str(supplier.id))
        self.assertEqual(request.entity_name, "Acme Supplies")

    @patch("apps.suppliers.services.supplier_accounting_service.create_default_entity_accounts")
    def test_create_supplier_rolls_back_on_failure(self, mock_create):
        mock_create.side_effect = Exception("Config missing")
        from apps.suppliers.models import Supplier
        from apps.suppliers.services import create_supplier

        with self.assertRaises(Exception):
            create_supplier(
                self.user,
                {
                    "branch_id": str(self.branch.id),
                    "name": "Failed Supplier",
                },
            )
        self.assertFalse(Supplier.objects.filter(name="Failed Supplier").exists())


class SupplierInvoiceAccountingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="SI Test Org")
        cls.branch = Branch.objects.create(organization=cls.org, name="Main", code="simain")
        cls.user = User.objects.create_user(
            email="si@example.com",
            username="siuser",
            password="testpass123",
            is_staff=True,
            organization=cls.org,
            branch=cls.branch,
        )

    @patch("apps.suppliers.services.supplier_invoice_accounting_service.create_supplier_invoice")
    @patch("apps.suppliers.services.supplier_invoice_accounting_service.get_configured_account")
    def test_post_supplier_invoice(self, mock_get_account, mock_create_invoice):
        mock_get_account.return_value = _make_mock_account()
        mock_create_invoice.return_value = _make_mock_journal()

        lpo = MagicMock()
        lpo.id = UUID("00000000-0000-0000-0000-000000000010")
        lpo.lpo_number = "LPO-20260509-0001"
        lpo.status = "received"
        lpo.total = Decimal("1500000.00")
        lpo.currency = "UGX"
        lpo.branch_id = cls.branch.id
        lpo.supplier = MagicMock()
        lpo.supplier.id = UUID("00000000-0000-0000-0000-000000000020")
        lpo.created_by_id = cls.user.id
        lpo.delivered_at = date.today()

        from apps.suppliers.services.supplier_invoice_accounting_service import (
            post_supplier_invoice,
        )

        post_supplier_invoice(lpo)

        mock_create_invoice.assert_called_once()
        call_kwargs = mock_create_invoice.call_args.kwargs
        self.assertEqual(call_kwargs["amount"], Decimal("1500000.00"))
        self.assertEqual(call_kwargs["supplier_id"], str(lpo.supplier.id))
        self.assertEqual(call_kwargs["currency"], "UGX")

    def test_post_cancelled_lpo_raises(self):
        lpo = MagicMock()
        lpo.status = "cancelled"
        lpo.total = Decimal("100.00")

        from apps.suppliers.services.supplier_invoice_accounting_service import (
            post_supplier_invoice,
        )

        with self.assertRaises(ValueError):
            post_supplier_invoice(lpo)

    @patch("apps.suppliers.services.supplier_invoice_accounting_service.create_and_post_journal")
    @patch("apps.suppliers.services.supplier_invoice_accounting_service.get_configured_account")
    def test_post_supplier_invoice_with_vat(self, mock_get_account, mock_post_journal):
        mock_get_account.return_value = _make_mock_account()
        mock_post_journal.return_value = _make_mock_journal()

        lpo = MagicMock()
        lpo.id = UUID("00000000-0000-0000-0000-000000000011")
        lpo.lpo_number = "LPO-VAT-0001"
        lpo.status = "received"
        lpo.total = Decimal("1180000.00")
        lpo.currency = "UGX"
        lpo.branch_id = cls.branch.id
        lpo.supplier = MagicMock()
        lpo.supplier.id = UUID("00000000-0000-0000-0000-000000000021")
        lpo.created_by_id = cls.user.id
        lpo.delivered_at = date.today()

        from apps.suppliers.services.supplier_invoice_accounting_service import (
            post_supplier_invoice_with_tax,
        )

        post_supplier_invoice_with_tax(
            lpo,
            net_amount=Decimal("1000000.00"),
            tax_amount=Decimal("180000.00"),
        )

        mock_post_journal.assert_called_once()
        call_kwargs = mock_post_journal.call_args.kwargs
        self.assertEqual(len(call_kwargs["lines"]), 3)


class SupplierPaymentAccountingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="SP Test Org")
        cls.branch = Branch.objects.create(organization=cls.org, name="Main", code="spmain")
        cls.user = User.objects.create_user(
            email="sp@example.com",
            username="spuser",
            password="testpass123",
            is_staff=True,
            organization=cls.org,
            branch=cls.branch,
        )

    @patch("apps.suppliers.services.supplier_payment_accounting_service.allocate_supplier_payment")
    @patch("apps.suppliers.services.supplier_payment_accounting_service._resolve_cash_account")
    def test_post_supplier_payment_ugx(self, mock_resolve_cash, mock_allocate):
        mock_resolve_cash.return_value = _make_mock_account()
        mock_allocate.return_value = _make_mock_journal()

        supplier = MagicMock()
        supplier.id = UUID("00000000-0000-0000-0000-000000000030")

        from apps.suppliers.services.supplier_payment_accounting_service import (
            post_supplier_payment,
        )

        post_supplier_payment(
            payment_id="PAY-001",
            supplier=supplier,
            amount=Decimal("500000.00"),
            payment_date=date.today(),
            payment_method="bank_transfer",
            branch_id=self.branch.id,
            created_by_id=self.user.id,
            currency="UGX",
        )

        mock_allocate.assert_called_once()
        call_kwargs = mock_allocate.call_args.kwargs
        self.assertEqual(call_kwargs["amount"], Decimal("500000.00"))
        self.assertEqual(call_kwargs["currency"], "UGX")
        self.assertIsNone(call_kwargs["original_foreign_amount"])

    @patch("apps.suppliers.services.supplier_payment_accounting_service.get_exchange_rate")
    @patch("apps.suppliers.services.supplier_payment_accounting_service.allocate_supplier_payment")
    @patch("apps.suppliers.services.supplier_payment_accounting_service._resolve_cash_account")
    def test_post_supplier_payment_forex(self, mock_resolve_cash, mock_allocate, mock_get_rate):
        mock_resolve_cash.return_value = _make_mock_account()
        mock_allocate.return_value = _make_mock_journal()
        mock_get_rate.return_value = Decimal("3700.000000")

        supplier = MagicMock()
        supplier.id = UUID("00000000-0000-0000-0000-000000000031")

        from apps.suppliers.services.supplier_payment_accounting_service import (
            post_supplier_payment,
        )

        post_supplier_payment(
            payment_id="PAY-FX-001",
            supplier=supplier,
            amount=Decimal("500.00"),
            payment_date=date.today(),
            payment_method="bank_transfer",
            branch_id=self.branch.id,
            created_by_id=self.user.id,
            currency="USD",
            invoice_date=date(2026, 4, 1),
        )

        call_kwargs = mock_allocate.call_args.kwargs
        self.assertEqual(call_kwargs["currency"], "USD")
        self.assertEqual(call_kwargs["original_foreign_amount"], Decimal("500.00"))
        self.assertEqual(call_kwargs["original_exchange_rate"], Decimal("3700.000000"))


class SupplierInvoiceReversalTest(TestCase):
    @patch("apps.suppliers.services.supplier_invoice_accounting_service.reverse_journal_entry")
    @patch("apps.suppliers.services.supplier_invoice_accounting_service.JournalRepository")
    def test_reverse_supplier_invoice(self, mock_repo_cls, mock_reverse):
        mock_repo_cls.find_existing.return_value = _make_mock_journal()
        mock_reverse.return_value = _make_mock_journal()

        lpo = MagicMock()
        lpo.id = UUID("00000000-0000-0000-0000-000000000040")
        lpo.lpo_number = "LPO-REV-0001"

        from apps.suppliers.services.supplier_invoice_accounting_service import (
            reverse_supplier_invoice,
        )

        reverse_supplier_invoice(
            lpo,
            reversal_date=date.today(),
            created_by_id=UUID("00000000-0000-0000-0000-000000000050"),
        )

        mock_reverse.assert_called_once()

    @patch("apps.suppliers.services.supplier_invoice_accounting_service.JournalRepository")
    def test_reverse_missing_journal_raises(self, mock_repo_cls):
        mock_repo_cls.find_existing.return_value = None

        lpo = MagicMock()
        lpo.id = UUID("00000000-0000-0000-0000-000000000041")
        lpo.lpo_number = "LPO-MISSING-0001"

        from apps.suppliers.services.supplier_invoice_accounting_service import (
            reverse_supplier_invoice,
        )

        with self.assertRaises(ValueError):
            reverse_supplier_invoice(
                lpo,
                reversal_date=date.today(),
            )


class SupplierPaymentReversalTest(TestCase):
    @patch("apps.suppliers.services.supplier_payment_accounting_service.reverse_journal_entry")
    @patch("apps.suppliers.services.supplier_payment_accounting_service.JournalRepository")
    def test_reverse_supplier_payment(self, mock_repo_cls, mock_reverse):
        mock_repo_cls.find_existing.return_value = _make_mock_journal()
        mock_reverse.return_value = _make_mock_journal()

        from apps.suppliers.services.supplier_payment_accounting_service import (
            reverse_supplier_payment,
        )

        reverse_supplier_payment(
            payment_id="PAY-REV-001",
            reversal_date=date.today(),
            created_by_id=UUID("00000000-0000-0000-0000-000000000060"),
        )

        mock_reverse.assert_called_once()
