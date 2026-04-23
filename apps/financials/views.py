from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.models import Job
from apps.accounts.permissions import IsJobManager
from apps.organization.models import Branch

from .models import Invoice, InvoicePayment, Requisition
from .serializers import (
    InvoiceListSerializer,
    InvoiceDetailSerializer,
    InvoiceCreateWriteSerializer,
    InvoicePatchWriteSerializer,
    InvoicePaymentWriteSerializer,
    InvoicePaymentSerializer,
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
