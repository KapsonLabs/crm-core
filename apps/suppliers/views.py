from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.financials.models import Requisition
from apps.jobs.models import Job

from .models import LocalPurchaseOrderItem

from .serializers import (
    LocalPurchaseOrderCreateWriteSerializer,
    LocalPurchaseOrderItemPatchWriteSerializer,
    LocalPurchaseOrderItemSerializer,
    LocalPurchaseOrderItemWriteSerializer,
    LocalPurchaseOrderPatchWriteSerializer,
    LocalPurchaseOrderReceiveWriteSerializer,
    LocalPurchaseOrderSerializer,
    LocalPurchaseOrderTransitionWriteSerializer,
    SupplierCreateWriteSerializer,
    SupplierPatchWriteSerializer,
    SupplierSerializer,
)
from .services import (
    create_lpo_item,
    create_lpo_with_items,
    create_supplier,
    delete_lpo,
    delete_lpo_item,
    delete_supplier,
    lpos_visible_queryset,
    patch_local_purchase_order,
    receive_lpo_lines,
    suppliers_visible_queryset,
    transition_lpo_status,
    update_lpo_item,
    update_supplier,
)


def _bad_request(message):
    return Response({'status': 400, 'message': message}, status=status.HTTP_400_BAD_REQUEST)


def _forbidden(message='Permission denied.'):
    return Response({'status': 403, 'message': message}, status=status.HTTP_403_FORBIDDEN)


class SupplierListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = suppliers_visible_queryset(request.user).order_by('name')
        if request.query_params.get('is_active') is not None:
            active = request.query_params.get('is_active').lower() == 'true'
            qs = qs.filter(is_active=active)
        bid = request.query_params.get('branch_id')
        if bid:
            qs = qs.filter(branch_id=bid)
        return Response(
            {'status': 200, 'data': SupplierSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        ser = SupplierCreateWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            supplier = create_supplier(request.user, ser.validated_data)
        except ValueError as e:
            return _bad_request(str(e))
        return Response(
            {'status': 201, 'data': SupplierSerializer(supplier).data},
            status=status.HTTP_201_CREATED,
        )


class SupplierDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        return get_object_or_404(suppliers_visible_queryset(request.user), pk=pk)

    def get(self, request, pk):
        supplier = self.get_object(request, pk)
        return Response(
            {'status': 200, 'data': SupplierSerializer(supplier).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        supplier = self.get_object(request, pk)
        ser = SupplierPatchWriteSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_supplier(supplier, request.user, ser.validated_data, partial=True)
        except ValueError as e:
            return _bad_request(str(e))
        except PermissionError as e:
            return _forbidden(str(e))
        supplier.refresh_from_db()
        return Response(
            {'status': 200, 'data': SupplierSerializer(supplier).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        supplier = self.get_object(request, pk)
        try:
            delete_supplier(supplier, request.user)
        except PermissionError as e:
            return _forbidden(str(e))
        except ValueError as e:
            return _bad_request(str(e))
        return Response(status=status.HTTP_204_NO_CONTENT)


class LocalPurchaseOrderListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = lpos_visible_queryset(request.user).order_by('-created_at')
        st = request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        sid = request.query_params.get('supplier_id')
        if sid:
            qs = qs.filter(supplier_id=sid)
        bid = request.query_params.get('branch_id')
        if bid:
            qs = qs.filter(branch_id=bid)
        return Response(
            {'status': 200, 'data': LocalPurchaseOrderSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        ser = LocalPurchaseOrderCreateWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            lpo = create_lpo_with_items(request.user, ser.validated_data)
        except ValueError as e:
            return _bad_request(str(e))
        except DjangoValidationError as e:
            data = getattr(e, 'message_dict', None) or {'non_field_errors': list(e.messages)}
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        except Job.DoesNotExist:
            return _bad_request('Job not found.')
        except Requisition.DoesNotExist:
            return _bad_request('Requisition not found.')
        lpo = lpos_visible_queryset(request.user).get(pk=lpo.pk)
        return Response(
            {'status': 201, 'data': LocalPurchaseOrderSerializer(lpo).data},
            status=status.HTTP_201_CREATED,
        )


class LocalPurchaseOrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        return get_object_or_404(lpos_visible_queryset(request.user), pk=pk)

    def get(self, request, pk):
        lpo = self.get_object(request, pk)
        return Response(
            {'status': 200, 'data': LocalPurchaseOrderSerializer(lpo).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        lpo = self.get_object(request, pk)
        ser = LocalPurchaseOrderPatchWriteSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            patch_local_purchase_order(lpo, request.user, ser.validated_data, partial=True)
        except ValueError as e:
            return _bad_request(str(e))
        except DjangoValidationError as e:
            data = getattr(e, 'message_dict', None) or {'non_field_errors': list(e.messages)}
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        lpo = lpos_visible_queryset(request.user).get(pk=lpo.pk)
        return Response(
            {'status': 200, 'data': LocalPurchaseOrderSerializer(lpo).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        lpo = self.get_object(request, pk)
        try:
            delete_lpo(lpo, request.user)
        except ValueError as e:
            return _bad_request(str(e))
        except PermissionError as e:
            return _forbidden(str(e))
        return Response(status=status.HTTP_204_NO_CONTENT)


class LocalPurchaseOrderTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        lpo = get_object_or_404(lpos_visible_queryset(request.user), pk=pk)
        ser = LocalPurchaseOrderTransitionWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            transition_lpo_status(lpo, request.user, ser.validated_data['status'])
        except ValueError as e:
            return _bad_request(str(e))
        lpo = lpos_visible_queryset(request.user).get(pk=lpo.pk)
        return Response(
            {'status': 200, 'data': LocalPurchaseOrderSerializer(lpo).data},
            status=status.HTTP_200_OK,
        )


class LocalPurchaseOrderReceiveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        lpo = get_object_or_404(lpos_visible_queryset(request.user), pk=pk)
        ser = LocalPurchaseOrderReceiveWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            receive_lpo_lines(lpo, request.user, ser.validated_data['lines'])
        except ValueError as e:
            return _bad_request(str(e))
        except DjangoValidationError as e:
            data = getattr(e, 'message_dict', None) or {'non_field_errors': list(e.messages)}
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        lpo = lpos_visible_queryset(request.user).get(pk=lpo.pk)
        return Response(
            {'status': 200, 'data': LocalPurchaseOrderSerializer(lpo).data},
            status=status.HTTP_200_OK,
        )


class LocalPurchaseOrderItemListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lpo_pk):
        lpo = get_object_or_404(lpos_visible_queryset(request.user), pk=lpo_pk)
        qs = (
            LocalPurchaseOrderItem.objects.filter(lpo=lpo, deleted_status=False)
            .select_related('product')
            .order_by('created_at', 'id')
        )
        return Response(
            {'status': 200, 'data': LocalPurchaseOrderItemSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request, lpo_pk):
        lpo = get_object_or_404(lpos_visible_queryset(request.user), pk=lpo_pk)
        ser = LocalPurchaseOrderItemWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            item = create_lpo_item(lpo, request.user, ser.validated_data)
        except ValueError as e:
            return _bad_request(str(e))
        except DjangoValidationError as e:
            data = getattr(e, 'message_dict', None) or {'non_field_errors': list(e.messages)}
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'status': 201, 'data': LocalPurchaseOrderItemSerializer(item).data},
            status=status.HTTP_201_CREATED,
        )


class LocalPurchaseOrderItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _item(self, request, lpo_pk, pk):
        get_object_or_404(lpos_visible_queryset(request.user), pk=lpo_pk)
        return get_object_or_404(
            LocalPurchaseOrderItem.objects.filter(lpo_id=lpo_pk, deleted_status=False),
            pk=pk,
        )

    def get(self, request, lpo_pk, pk):
        item = self._item(request, lpo_pk, pk)
        return Response(
            {'status': 200, 'data': LocalPurchaseOrderItemSerializer(item).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, lpo_pk, pk):
        item = self._item(request, lpo_pk, pk)
        ser = LocalPurchaseOrderItemPatchWriteSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_lpo_item(item, request.user, ser.validated_data, partial=True)
        except ValueError as e:
            return _bad_request(str(e))
        except DjangoValidationError as e:
            data = getattr(e, 'message_dict', None) or {'non_field_errors': list(e.messages)}
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        item.refresh_from_db()
        return Response(
            {'status': 200, 'data': LocalPurchaseOrderItemSerializer(item).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, lpo_pk, pk):
        item = self._item(request, lpo_pk, pk)
        try:
            delete_lpo_item(item, request.user)
        except ValueError as e:
            return _bad_request(str(e))
        return Response(status=status.HTTP_204_NO_CONTENT)
