from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.financials.models import Invoice, InvoicePayment
from apps.jobs.models import Job
from apps.organization.models import Branch, Organization


def _make_mock_account(account_id="00000000-0000-0000-0000-000000000001"):
    from uuid import UUID

    account = MagicMock()
    account.id = UUID(account_id)
    account.code = "TEST"
    return account


def _make_mock_journal():
    journal = MagicMock()
    journal.id = "00000000-0000-0000-0000-000000000099"
    journal.status = "posted"
    return journal


class CustomerSubledgerCreationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Test Org")
        cls.branch = Branch.objects.create(organization=cls.org, name="Main", code="main")
        cls.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
            is_staff=True,
            organization=cls.org,
            branch=cls.branch,
        )

    @patch("apps.customers.services.customer_accounting_service.create_default_entity_accounts")
    def test_create_customer_creates_subledger(self, mock_create):
        mock_create.return_value = [MagicMock()]
        from apps.customers.services import create_customer

        customer = create_customer(
            self.user,
            {
                "branch_id": str(self.branch.id),
                "first_name": "John",
                "last_name": "Doe",
                "phone_number": "+256700000000",
            },
        )
        self.assertIsNotNone(customer.id)
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        request = call_kwargs.kwargs["request"]
        self.assertEqual(request.entity_type, "customer")
        self.assertEqual(request.entity_id, str(customer.id))
        self.assertEqual(request.branch, self.branch.id)

    @patch("apps.customers.services.customer_accounting_service.create_default_entity_accounts")
    def test_create_customer_rolls_back_on_subledger_failure(self, mock_create):
        mock_create.side_effect = Exception("Accounting config missing")
        from apps.customers.services import create_customer

        with self.assertRaises(Exception):
            create_customer(
                self.user,
                {
                    "branch_id": str(self.branch.id),
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "phone_number": "+256700000001",
                },
            )
        self.assertFalse(Customer.objects.filter(first_name="Jane", last_name="Doe").exists())


class InvoiceAccountingPostingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Test Org")
        cls.branch = Branch.objects.create(organization=cls.org, name="Main", code="main")
        cls.user = User.objects.create_user(
            email="inv@example.com",
            username="invuser",
            password="testpass123",
            is_staff=True,
            organization=cls.org,
            branch=cls.branch,
        )
        cls.customer = Customer.objects.create(
            organization=cls.org,
            branch=cls.branch,
            first_name="Test",
            last_name="Customer",
            phone_number="+256700000000",
        )
        cls.job = Job.objects.create(
            customer=cls.customer,
            organization=cls.org,
            branch=cls.branch,
            created_by=cls.user,
            title="Test Job",
        )

    @patch("apps.financials.services.invoice_accounting_service.create_receivable_invoice")
    @patch("apps.financials.services.invoice_accounting_service.get_configured_account")
    def test_post_customer_invoice_no_tax(self, mock_get_account, mock_create_recv):
        mock_get_account.return_value = _make_mock_account()
        mock_create_recv.return_value = _make_mock_journal()

        invoice = Invoice.objects.create(
            job=self.job,
            organization=self.org,
            branch=self.branch,
            created_by=self.user,
            invoice_number="INV-TEST-0001",
            status=Invoice.STATUS_SENT,
            currency="UGX",
            subtotal=Decimal("500000.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("500000.00"),
            issued_at=date.today(),
        )

        from apps.financials.services.invoice_accounting_service import post_customer_invoice

        post_customer_invoice(invoice)

        mock_create_recv.assert_called_once()
        call_kwargs = mock_create_recv.call_args.kwargs
        self.assertEqual(call_kwargs["amount"], Decimal("500000.00"))
        self.assertEqual(call_kwargs["customer_id"], str(self.customer.id))
        self.assertEqual(call_kwargs["currency"], "UGX")
        self.assertEqual(
            call_kwargs["idempotency_key"],
            f"receivable-invoice:INV-TEST-0001",
        )

    @patch("apps.financials.services.invoice_accounting_service.create_and_post_journal")
    @patch("apps.financials.services.invoice_accounting_service.get_configured_account")
    def test_post_customer_invoice_with_vat(self, mock_get_account, mock_post_journal):
        mock_get_account.return_value = _make_mock_account()
        mock_post_journal.return_value = _make_mock_journal()

        invoice = Invoice.objects.create(
            job=self.job,
            organization=self.org,
            branch=self.branch,
            created_by=self.user,
            invoice_number="INV-TEST-0002",
            status=Invoice.STATUS_SENT,
            currency="UGX",
            subtotal=Decimal("500000.00"),
            tax_amount=Decimal("90000.00"),
            total=Decimal("590000.00"),
            issued_at=date.today(),
        )

        from apps.financials.services.invoice_accounting_service import post_customer_invoice

        post_customer_invoice(invoice)

        mock_post_journal.assert_called_once()
        call_kwargs = mock_post_journal.call_args.kwargs
        self.assertEqual(len(call_kwargs["lines"]), 3)
        self.assertEqual(
            call_kwargs["idempotency_key"],
            "customer-invoice:INV-TEST-0002",
        )

    def test_post_void_invoice_raises(self):
        invoice = Invoice.objects.create(
            job=self.job,
            organization=self.org,
            branch=self.branch,
            created_by=self.user,
            invoice_number="INV-TEST-VOID",
            status=Invoice.STATUS_VOID,
            currency="UGX",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("100.00"),
            issued_at=date.today(),
        )

        from apps.financials.services.invoice_accounting_service import post_customer_invoice

        with self.assertRaises(ValueError, msg="Cannot post a voided invoice."):
            post_customer_invoice(invoice)

    def test_post_zero_total_invoice_raises(self):
        invoice = Invoice.objects.create(
            job=self.job,
            organization=self.org,
            branch=self.branch,
            created_by=self.user,
            invoice_number="INV-TEST-ZERO",
            status=Invoice.STATUS_SENT,
            currency="UGX",
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("0.00"),
            issued_at=date.today(),
        )

        from apps.financials.services.invoice_accounting_service import post_customer_invoice

        with self.assertRaises(ValueError):
            post_customer_invoice(invoice)

    @patch("apps.financials.services.invoice_accounting_service.create_receivable_invoice")
    @patch("apps.financials.services.invoice_accounting_service.get_configured_account")
    def test_post_multi_currency_invoice(self, mock_get_account, mock_create_recv):
        mock_get_account.return_value = _make_mock_account()
        mock_create_recv.return_value = _make_mock_journal()

        invoice = Invoice.objects.create(
            job=self.job,
            organization=self.org,
            branch=self.branch,
            created_by=self.user,
            invoice_number="INV-TEST-USD",
            status=Invoice.STATUS_SENT,
            currency="USD",
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("1000.00"),
            issued_at=date.today(),
        )

        from apps.financials.services.invoice_accounting_service import post_customer_invoice

        post_customer_invoice(invoice)

        call_kwargs = mock_create_recv.call_args.kwargs
        self.assertEqual(call_kwargs["currency"], "USD")
        self.assertEqual(call_kwargs["amount"], Decimal("1000.00"))


class CustomerPaymentAccountingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Pay Test Org")
        cls.branch = Branch.objects.create(organization=cls.org, name="Main", code="paymain")
        cls.user = User.objects.create_user(
            email="pay@example.com",
            username="payuser",
            password="testpass123",
            is_staff=True,
            organization=cls.org,
            branch=cls.branch,
        )
        cls.customer = Customer.objects.create(
            organization=cls.org,
            branch=cls.branch,
            first_name="Pay",
            last_name="Customer",
            phone_number="+256700000000",
        )
        cls.job = Job.objects.create(
            customer=cls.customer,
            organization=cls.org,
            branch=cls.branch,
            created_by=cls.user,
            title="Pay Job",
        )
        cls.invoice = Invoice.objects.create(
            job=cls.job,
            organization=cls.org,
            branch=cls.branch,
            created_by=cls.user,
            invoice_number="INV-PAY-0001",
            status=Invoice.STATUS_SENT,
            currency="UGX",
            subtotal=Decimal("500000.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("500000.00"),
            issued_at=date.today(),
        )

    @patch("apps.financials.services.customer_payment_accounting_service.allocate_customer_payment")
    @patch("apps.financials.services.customer_payment_accounting_service._resolve_cash_account")
    def test_post_customer_payment_ugx(self, mock_resolve_cash, mock_allocate):
        mock_resolve_cash.return_value = _make_mock_account()
        mock_allocate.return_value = _make_mock_journal()

        payment = InvoicePayment.objects.create(
            invoice=self.invoice,
            amount=Decimal("200000.00"),
            method="bank_transfer",
            recorded_by=self.user,
        )

        from apps.financials.services.customer_payment_accounting_service import (
            post_customer_payment,
        )

        post_customer_payment(payment)

        mock_allocate.assert_called_once()
        call_kwargs = mock_allocate.call_args.kwargs
        self.assertEqual(call_kwargs["amount"], Decimal("200000.00"))
        self.assertEqual(call_kwargs["currency"], "UGX")
        self.assertIsNone(call_kwargs["original_foreign_amount"])
        self.assertIsNone(call_kwargs["original_exchange_rate"])

    @patch("apps.financials.services.customer_payment_accounting_service.get_exchange_rate")
    @patch("apps.financials.services.customer_payment_accounting_service.allocate_customer_payment")
    @patch("apps.financials.services.customer_payment_accounting_service._resolve_cash_account")
    def test_post_customer_payment_foreign_currency(
        self, mock_resolve_cash, mock_allocate, mock_get_rate
    ):
        mock_resolve_cash.return_value = _make_mock_account()
        mock_allocate.return_value = _make_mock_journal()
        mock_get_rate.return_value = Decimal("3700.000000")

        usd_invoice = Invoice.objects.create(
            job=self.job,
            organization=self.org,
            branch=self.branch,
            created_by=self.user,
            invoice_number="INV-PAY-USD",
            status=Invoice.STATUS_SENT,
            currency="USD",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("100.00"),
            issued_at=date.today(),
        )
        payment = InvoicePayment.objects.create(
            invoice=usd_invoice,
            amount=Decimal("100.00"),
            method="bank_transfer",
            recorded_by=self.user,
        )

        from apps.financials.services.customer_payment_accounting_service import (
            post_customer_payment,
        )

        post_customer_payment(payment)

        call_kwargs = mock_allocate.call_args.kwargs
        self.assertEqual(call_kwargs["currency"], "USD")
        self.assertEqual(call_kwargs["original_foreign_amount"], Decimal("100.00"))
        self.assertEqual(call_kwargs["original_exchange_rate"], Decimal("3700.000000"))


class InvoiceReversalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Rev Test Org")
        cls.branch = Branch.objects.create(organization=cls.org, name="Main", code="revmain")
        cls.user = User.objects.create_user(
            email="rev@example.com",
            username="revuser",
            password="testpass123",
            is_staff=True,
            organization=cls.org,
            branch=cls.branch,
        )
        cls.customer = Customer.objects.create(
            organization=cls.org,
            branch=cls.branch,
            first_name="Rev",
            last_name="Customer",
            phone_number="+256700000000",
        )
        cls.job = Job.objects.create(
            customer=cls.customer,
            organization=cls.org,
            branch=cls.branch,
            created_by=cls.user,
            title="Rev Job",
        )

    @patch("apps.financials.services.invoice_accounting_service.reverse_journal_entry")
    @patch("apps.financials.services.invoice_accounting_service.JournalRepository")
    def test_reverse_customer_invoice(self, mock_repo_cls, mock_reverse):
        mock_journal = _make_mock_journal()
        mock_repo_cls.find_existing.return_value = mock_journal
        mock_reverse.return_value = _make_mock_journal()

        invoice = Invoice.objects.create(
            job=self.job,
            organization=self.org,
            branch=self.branch,
            created_by=self.user,
            invoice_number="INV-REV-0001",
            status=Invoice.STATUS_SENT,
            currency="UGX",
            subtotal=Decimal("500000.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("500000.00"),
            issued_at=date.today(),
        )

        from apps.financials.services.invoice_accounting_service import (
            reverse_customer_invoice,
        )

        reverse_customer_invoice(
            invoice,
            reversal_date=date.today(),
            created_by_id=self.user.id,
        )

        mock_reverse.assert_called_once()

    @patch("apps.financials.services.invoice_accounting_service.JournalRepository")
    def test_reverse_missing_journal_raises(self, mock_repo_cls):
        mock_repo_cls.find_existing.return_value = None

        invoice = Invoice.objects.create(
            job=self.job,
            organization=self.org,
            branch=self.branch,
            created_by=self.user,
            invoice_number="INV-REV-MISSING",
            status=Invoice.STATUS_SENT,
            currency="UGX",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("100.00"),
            issued_at=date.today(),
        )

        from apps.financials.services.invoice_accounting_service import (
            reverse_customer_invoice,
        )

        with self.assertRaises(ValueError):
            reverse_customer_invoice(
                invoice,
                reversal_date=date.today(),
                created_by_id=self.user.id,
            )


class PaymentReversalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="PayRev Test Org")
        cls.branch = Branch.objects.create(organization=cls.org, name="Main", code="prvmain")
        cls.user = User.objects.create_user(
            email="payrev@example.com",
            username="payrevuser",
            password="testpass123",
            is_staff=True,
            organization=cls.org,
            branch=cls.branch,
        )
        cls.customer = Customer.objects.create(
            organization=cls.org,
            branch=cls.branch,
            first_name="PayRev",
            last_name="Customer",
            phone_number="+256700000000",
        )
        cls.job = Job.objects.create(
            customer=cls.customer,
            organization=cls.org,
            branch=cls.branch,
            created_by=cls.user,
            title="PayRev Job",
        )
        cls.invoice = Invoice.objects.create(
            job=cls.job,
            organization=cls.org,
            branch=cls.branch,
            created_by=cls.user,
            invoice_number="INV-PAYREV-0001",
            status=Invoice.STATUS_SENT,
            currency="UGX",
            subtotal=Decimal("500000.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("500000.00"),
            issued_at=date.today(),
        )

    @patch("apps.financials.services.customer_payment_accounting_service.reverse_journal_entry")
    @patch("apps.financials.services.customer_payment_accounting_service.JournalRepository")
    def test_reverse_customer_payment(self, mock_repo_cls, mock_reverse):
        mock_repo_cls.find_existing.return_value = _make_mock_journal()
        mock_reverse.return_value = _make_mock_journal()

        payment = InvoicePayment.objects.create(
            invoice=self.invoice,
            amount=Decimal("200000.00"),
            method="bank_transfer",
            recorded_by=self.user,
        )

        from apps.financials.services.customer_payment_accounting_service import (
            reverse_customer_payment,
        )

        reverse_customer_payment(
            payment,
            reversal_date=date.today(),
            created_by_id=self.user.id,
        )

        mock_reverse.assert_called_once()
