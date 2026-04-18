from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Customer, CustomerFeedback
from apps.organization.models import Branch

from .serializers import (
    CustomerSerializer,
    CustomerCreateWriteSerializer,
    CustomerPatchWriteSerializer,
    CustomerFeedbackSerializer,
    CustomerFeedbackWriteSerializer,
    CustomerFeedbackPatchWriteSerializer,
)
from .services import (
    customers_visible_queryset,
    feedback_visible_queryset,
    create_customer,
    update_customer,
    delete_customer,
    create_feedback,
    update_feedback,
    delete_feedback,
)


def _bad_request(message):
    return Response({'status': 400, 'message': message}, status=status.HTTP_400_BAD_REQUEST)


def _forbidden(message='Permission denied.'):
    return Response({'status': 403, 'message': message}, status=status.HTTP_403_FORBIDDEN)


class CustomerListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = customers_visible_queryset(request.user).order_by('last_name', 'first_name')
        if request.query_params.get('is_active') is not None:
            active = request.query_params.get('is_active').lower() == 'true'
            qs = qs.filter(is_active=active)
        bid = request.query_params.get('branch_id')
        if bid:
            qs = qs.filter(branch_id=bid)
        return Response(
            {'status': 200, 'data': CustomerSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        ser = CustomerCreateWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            customer = create_customer(request.user, ser.validated_data)
        except ValueError as e:
            return _bad_request(str(e))
        except Branch.DoesNotExist:
            return _bad_request('Invalid branch.')
        return Response(
            {'status': 201, 'data': CustomerSerializer(customer).data},
            status=status.HTTP_201_CREATED,
        )


class CustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        return get_object_or_404(customers_visible_queryset(request.user), pk=pk)

    def get(self, request, pk):
        customer = self.get_object(request, pk)
        return Response(
            {'status': 200, 'data': CustomerSerializer(customer).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        customer = self.get_object(request, pk)
        ser = CustomerPatchWriteSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_customer(customer, request.user, ser.validated_data, partial=True)
        except ValueError as e:
            return _bad_request(str(e))
        except PermissionError as e:
            return _forbidden(str(e))
        customer.refresh_from_db()
        return Response(
            {'status': 200, 'data': CustomerSerializer(customer).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        customer = self.get_object(request, pk)
        try:
            delete_customer(customer, request.user)
        except PermissionError as e:
            return _forbidden(str(e))
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerFeedbackListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        customer_id = request.query_params.get('customer_id')
        qs = feedback_visible_queryset(request.user, customer_id=customer_id)
        qs = qs.order_by('-created_at')
        return Response(
            {'status': 200, 'data': CustomerFeedbackSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        ser = CustomerFeedbackWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            fb = create_feedback(request.user, ser.validated_data)
        except ValueError as e:
            return _bad_request(str(e))
        except Customer.DoesNotExist:
            return _bad_request('Invalid customer.')
        return Response(
            {'status': 201, 'data': CustomerFeedbackSerializer(fb).data},
            status=status.HTTP_201_CREATED,
        )


class CustomerFeedbackDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        return get_object_or_404(feedback_visible_queryset(request.user), pk=pk)

    def get(self, request, pk):
        fb = self.get_object(request, pk)
        return Response(
            {'status': 200, 'data': CustomerFeedbackSerializer(fb).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        fb = self.get_object(request, pk)
        ser = CustomerFeedbackPatchWriteSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_feedback(fb, request.user, ser.validated_data, partial=True)
        except ValueError as e:
            return _bad_request(str(e))
        except PermissionError as e:
            return _forbidden(str(e))
        fb.refresh_from_db()
        return Response(
            {'status': 200, 'data': CustomerFeedbackSerializer(fb).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        fb = self.get_object(request, pk)
        try:
            delete_feedback(fb, request.user)
        except ValueError as e:
            return _bad_request(str(e))
        except PermissionError as e:
            return _forbidden(str(e))
        return Response(status=status.HTTP_204_NO_CONTENT)
