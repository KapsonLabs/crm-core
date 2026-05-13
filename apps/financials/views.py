from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.models import Job
from apps.accounts.permissions import IsJobManager
from apps.organization.models import Branch

from .models import BankAccount, Invoice, InvoicePayment, PaymentMethod, Requisition
from .serializers import (
    BankAccountSerializer,
    BankAccountWriteSerializer,
    InvoiceListSerializer,
    InvoiceDetailSerializer,
    InvoiceCreateWriteSerializer,
    InvoicePatchWriteSerializer,
    InvoicePaymentWriteSerializer,
    InvoicePaymentSerializer,
    PaymentMethodSerializer,
    PaymentMethodWriteSerializer,
    RequisitionSerializer,
    RequisitionCreateWriteSerializer,
    RequisitionPatchWriteSerializer,
)
from .services import (
    invoices_for_user,
    create_invoice,
    update_invoice,
    void_invoice,
    record_payment_for_invoice,
    delete_payment,
    requisitions_for_user,
    create_requisition,
    update_requisition,
    delete_requisition,
)
from .services.payment_method_service import create_payment_method
from .services.bank_account_service import create_bank_account


def _bad(message):
    return Response({'status': 400, 'message': message}, status=status.HTTP_400_BAD_REQUEST)


def _denied(message='Permission denied.'):
    return Response({'status': 403, 'message': message}, status=status.HTTP_403_FORBIDDEN)


class InvoiceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List invoices. Query params: status, branch_id (job branch), job_id."""
        qs = invoices_for_user(request.user)
        st = request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        bid = request.query_params.get('branch_id')
        if bid:
            qs = qs.filter(branch_id=bid)
        jid = request.query_params.get('job_id')
        if jid:
            qs = qs.filter(job_id=jid)
        qs = qs.order_by('branch_id', 'job__branch_id', '-issued_at', '-created_at')
        return Response(
            {'status': 200, 'data': InvoiceListSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        ser = InvoiceCreateWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            inv = create_invoice(request.user, ser.validated_data)
        except ValueError as e:
            return _bad(str(e))
        except Job.DoesNotExist:
            return _bad('Invalid job.')
        except Branch.DoesNotExist:
            return _bad('Invalid branch.')
        inv = invoices_for_user(request.user).prefetch_related('payments').get(pk=inv.pk)
        return Response(
            {'status': 201, 'data': InvoiceDetailSerializer(inv).data},
            status=status.HTTP_201_CREATED,
        )


class InvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in {'PATCH', 'DELETE'}:
            return [IsAuthenticated(), IsJobManager()]
        return [IsAuthenticated()]

    def get_object(self, request, pk):
        return get_object_or_404(invoices_for_user(request.user), pk=pk)

    def get(self, request, pk):
        inv = self.get_object(request, pk)
        inv = invoices_for_user(request.user).prefetch_related('payments').get(pk=inv.pk)
        return Response(
            {'status': 200, 'data': InvoiceDetailSerializer(inv).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        inv = self.get_object(request, pk)
        ser = InvoicePatchWriteSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_invoice(inv, request.user, ser.validated_data, partial=True)
        except ValueError as e:
            return _bad(str(e))
        except PermissionError as e:
            return _denied(str(e))
        inv = invoices_for_user(request.user).prefetch_related('payments').get(pk=inv.pk)
        return Response(
            {'status': 200, 'data': InvoiceDetailSerializer(inv).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        inv = self.get_object(request, pk)
        inv.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvoiceVoidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        inv = get_object_or_404(invoices_for_user(request.user), pk=pk)
        try:
            void_invoice(inv, request.user)
        except PermissionError as e:
            return _denied(str(e))
        inv = invoices_for_user(request.user).prefetch_related('payments').get(pk=inv.pk)
        return Response(
            {'status': 200, 'data': InvoiceDetailSerializer(inv).data},
            status=status.HTTP_200_OK,
        )


class InvoicePaymentListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsJobManager]

    def post(self, request):
        ser = InvoicePaymentWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        validated = ser.validated_data.copy()
        invoice_id = validated.pop('invoice_id')
        inv = get_object_or_404(invoices_for_user(request.user), pk=invoice_id)
        try:
            pay = record_payment_for_invoice(inv, request.user, validated)
        except ValueError as e:
            return _bad(str(e))
        except PermissionError as e:
            return _denied(str(e))
        inv = invoices_for_user(request.user).prefetch_related('payments').get(pk=inv.pk)
        return Response(
            {
                'status': 201,
                'data': InvoicePaymentSerializer(pay).data,
                'invoice': InvoiceDetailSerializer(inv).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        payment = get_object_or_404(InvoicePayment.objects.select_related('invoice'), pk=pk)
        try:
            delete_payment(payment, request.user)
        except PermissionError as e:
            return _denied(str(e))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentMethodListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Return branch-specific methods + global (branch=NULL) defaults
        qs = PaymentMethod.objects.filter(is_active=True)
        branch_id = request.query_params.get('branch_id') or getattr(request.user, 'branch_id', None)
        if branch_id:
            qs = qs.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))
        else:
            qs = qs.filter(branch__isnull=True)
        return Response(
            {'status': 200, 'data': PaymentMethodSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if not request.user.is_job_manager:
            return _denied('Only administrators or supervisors can create payment methods.')
        ser = PaymentMethodWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        vd = ser.validated_data
        try:
            method = create_payment_method(
                branch_id=vd.get('branch_id'),
                name=vd['name'],
                code=vd['code'],
                account_type=vd['account_type'],
                description=vd.get('description', ''),
                is_active=vd.get('is_active', True),
            )
        except ValueError as e:
            return _bad(str(e))
        return Response(
            {'status': 201, 'data': PaymentMethodSerializer(method).data},
            status=status.HTTP_201_CREATED,
        )


class PaymentMethodDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(PaymentMethod, pk=pk)

    def get(self, request, pk):
        method = self.get_object(pk)
        return Response(
            {'status': 200, 'data': PaymentMethodSerializer(method).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        if not request.user.is_job_manager:
            return _denied('Only administrators or supervisors can update payment methods.')
        method = self.get_object(pk)
        ser = PaymentMethodWriteSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        vd = ser.validated_data
        for field in ('name', 'description', 'is_active'):
            if field in vd:
                setattr(method, field, vd[field])
        method.save(update_fields=[f for f in ('name', 'description', 'is_active') if f in vd] + ['updated_at'])
        method.refresh_from_db()
        return Response(
            {'status': 200, 'data': PaymentMethodSerializer(method).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        if not request.user.is_job_manager:
            return _denied('Only administrators or supervisors can delete payment methods.')
        method = self.get_object(pk)
        method.is_active = False
        method.save(update_fields=['is_active', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class RequisitionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = requisitions_for_user(request.user)
        st = request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        bid = request.query_params.get('branch_id')
        if bid:
            qs = qs.filter(branch_id=bid)
        qs = qs.order_by('-created_at')
        return Response(
            {'status': 200, 'data': RequisitionSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        ser = RequisitionCreateWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            req = create_requisition(request.user, ser.validated_data)
        except ValueError as e:
            return _bad(str(e))
        except Job.DoesNotExist:
            return _bad('Invalid job.')
        except Branch.DoesNotExist:
            return _bad('Invalid branch.')
        return Response(
            {'status': 201, 'data': RequisitionSerializer(req).data},
            status=status.HTTP_201_CREATED,
        )


class RequisitionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        return get_object_or_404(requisitions_for_user(request.user), pk=pk)

    def get(self, request, pk):
        req = self.get_object(request, pk)
        return Response(
            {'status': 200, 'data': RequisitionSerializer(req).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        req = self.get_object(request, pk)
        ser = RequisitionPatchWriteSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_requisition(req, request.user, ser.validated_data, partial=True)
        except ValueError as e:
            return _bad(str(e))
        except PermissionError as e:
            return _denied(str(e))
        except Job.DoesNotExist:
            return _bad('Invalid job.')
        req.refresh_from_db()
        return Response(
            {'status': 200, 'data': RequisitionSerializer(req).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        req = self.get_object(request, pk)
        try:
            delete_requisition(req, request.user)
        except PermissionError as e:
            return _denied(str(e))
        return Response(status=status.HTTP_204_NO_CONTENT)


class BankAccountListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = BankAccount.objects.select_related('branch', 'payment_method__account').filter(is_active=True)
        branch_id = request.query_params.get('branch_id') or getattr(request.user, 'branch_id', None)
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return Response(
            {'status': 200, 'data': BankAccountSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if not request.user.is_job_manager:
            return _denied('Only administrators or supervisors can create bank accounts.')
        ser = BankAccountWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        vd = ser.validated_data
        try:
            bank = create_bank_account(
                branch_id=vd['branch_id'],
                bank_name=vd['bank_name'],
                account_name=vd['account_name'],
                account_number=vd['account_number'],
                currency=vd.get('currency', 'UGX'),
            )
        except ValueError as e:
            return _bad(str(e))
        bank = BankAccount.objects.select_related('branch', 'payment_method__account').get(pk=bank.pk)
        return Response(
            {'status': 201, 'data': BankAccountSerializer(bank).data},
            status=status.HTTP_201_CREATED,
        )


class BankAccountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(
            BankAccount.objects.select_related('branch', 'payment_method__account'),
            pk=pk,
        )

    def get(self, request, pk):
        bank = self.get_object(pk)
        return Response(
            {'status': 200, 'data': BankAccountSerializer(bank).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        if not request.user.is_job_manager:
            return _denied('Only administrators or supervisors can update bank accounts.')
        bank = self.get_object(pk)
        allowed = {'bank_name', 'account_name', 'currency', 'is_active'}
        data = {k: v for k, v in request.data.items() if k in allowed}
        for field, value in data.items():
            setattr(bank, field, value)
        if data:
            bank.save(update_fields=list(data.keys()) + ['updated_at'])
            bank.refresh_from_db()
        return Response(
            {'status': 200, 'data': BankAccountSerializer(bank).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        if not request.user.is_job_manager:
            return _denied('Only administrators or supervisors can deactivate bank accounts.')
        bank = self.get_object(pk)
        bank.is_active = False
        bank.save(update_fields=['is_active', 'updated_at'])
        if bank.payment_method:
            bank.payment_method.is_active = False
            bank.payment_method.save(update_fields=['is_active', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)