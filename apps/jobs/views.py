from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import Customer
from apps.organization.models import Organization

from .models import Job, JobAssignment
from .serializers import (
    ProductSerializer,
    ProductCreateWriteSerializer,
    ProductPatchWriteSerializer,
    JobListSerializer,
    JobDetailSerializer,
    JobCreateWriteSerializer,
    JobPatchWriteSerializer,
    JobAssignSerializer,
    JobCompleteSerializer,
    JobCloseSerializer,
)
from .services import (
    is_job_manager,
    job_queryset_for_user,
    products_visible_for_user,
    create_product,
    update_product,
    delete_product,
    create_job,
    update_job,
    assign_users_to_job,
    complete_job,
    close_job,
)


def _forbidden_manager():
    return Response(
        {'status': 403, 'message': 'Only administrators or supervisors can perform this action.'},
        status=status.HTTP_403_FORBIDDEN,
    )


def _bad_request(message):
    return Response({'status': 400, 'message': message}, status=status.HTTP_400_BAD_REQUEST)


def _job_detail_qs(user):
    return job_queryset_for_user(user)


class ProductListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = products_visible_for_user(request.user)
        if request.query_params.get('is_active') is not None:
            active = request.query_params.get('is_active').lower() == 'true'
            qs = qs.filter(is_active=active)
        kind = request.query_params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        qs = qs.order_by('name')
        return Response(
            {'status': 200, 'data': ProductSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if not is_job_manager(request.user):
            return _forbidden_manager()
        ser = ProductCreateWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            product = create_product(request.user, ser.validated_data)
        except ValueError as e:
            return _bad_request(str(e))
        except Organization.DoesNotExist:
            return _bad_request('Invalid organization.')
        return Response(
            {'status': 201, 'data': ProductSerializer(product).data},
            status=status.HTTP_201_CREATED,
        )


class ProductDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        return get_object_or_404(products_visible_for_user(request.user), pk=pk)

    def get(self, request, pk):
        obj = self.get_object(request, pk)
        return Response(
            {'status': 200, 'data': ProductSerializer(obj).data},
            status=status.HTTP_200_OK,
        )

    def put(self, request, pk):
        if not is_job_manager(request.user):
            return _forbidden_manager()
        obj = self.get_object(request, pk)
        ser = ProductCreateWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_product(obj, request.user, ser.validated_data, partial=False)
        except ValueError as e:
            return _bad_request(str(e))
        except PermissionError as e:
            return Response({'status': 403, 'message': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Organization.DoesNotExist:
            return _bad_request('Invalid organization.')
        obj.refresh_from_db()
        return Response(
            {'status': 200, 'data': ProductSerializer(obj).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        if not is_job_manager(request.user):
            return _forbidden_manager()
        obj = self.get_object(request, pk)
        ser = ProductPatchWriteSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_product(obj, request.user, ser.validated_data, partial=True)
        except ValueError as e:
            return _bad_request(str(e))
        except PermissionError as e:
            return Response({'status': 403, 'message': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Organization.DoesNotExist:
            return _bad_request('Invalid organization.')
        obj.refresh_from_db()
        return Response(
            {'status': 200, 'data': ProductSerializer(obj).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        if not is_job_manager(request.user):
            return _forbidden_manager()
        obj = self.get_object(request, pk)
        try:
            delete_product(obj, request.user)
        except ValueError as e:
            return _bad_request(str(e))
        except PermissionError as e:
            return Response({'status': 403, 'message': str(e)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = job_queryset_for_user(request.user).annotate(
            assignee_count=Count('assignments', distinct=True),
        )
        st = request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        if is_job_manager(request.user) and request.query_params.get('organization_id'):
            qs = qs.filter(organization_id=request.query_params.get('organization_id'))
        qs = qs.order_by('-created_at')
        return Response(
            {'status': 200, 'data': JobListSerializer(qs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        ser = JobCreateWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            job = create_job(request.user, ser.validated_data)
        except ValueError as e:
            return _bad_request(str(e))
        except (Organization.DoesNotExist, Customer.DoesNotExist):
            return _bad_request('Invalid customer or organization.')
        job = _job_detail_qs(request.user).annotate(
            assignee_count=Count('assignments', distinct=True),
        ).get(pk=job.pk)
        return Response(
            {'status': 201, 'data': JobDetailSerializer(job).data},
            status=status.HTTP_201_CREATED,
        )


class JobDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        qs = job_queryset_for_user(request.user)
        return get_object_or_404(qs, pk=pk)

    def get(self, request, pk):
        job = self.get_object(request, pk)
        return Response(
            {'status': 200, 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK,
        )

    def put(self, request, pk):
        job = self.get_object(request, pk)
        ser = JobCreateWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_job(request.user, job, ser.validated_data, partial=False)
        except ValueError as e:
            return _bad_request(str(e))
        except PermissionError as e:
            return Response({'status': 403, 'message': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except (Organization.DoesNotExist, Customer.DoesNotExist):
            return _bad_request('Invalid customer or organization.')
        job = _job_detail_qs(request.user).get(pk=job.pk)
        return Response(
            {'status': 200, 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        job = self.get_object(request, pk)
        ser = JobPatchWriteSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_job(request.user, job, ser.validated_data, partial=True)
        except ValueError as e:
            return _bad_request(str(e))
        except PermissionError as e:
            return Response({'status': 403, 'message': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except (Organization.DoesNotExist, Customer.DoesNotExist):
            return _bad_request('Invalid customer or organization.')
        job = _job_detail_qs(request.user).get(pk=job.pk)
        return Response(
            {'status': 200, 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        job = self.get_object(request, pk)
        if is_job_manager(request.user):
            job.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        if job.created_by_id == request.user.id and job.status == Job.STATUS_OPEN:
            job.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {'status': 403, 'message': 'You may only delete your own jobs while they are open.'},
            status=status.HTTP_403_FORBIDDEN,
        )


class JobAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_pk):
        if not is_job_manager(request.user):
            return _forbidden_manager()
        job = get_object_or_404(job_queryset_for_user(request.user), pk=job_pk)
        ser = JobAssignSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        user_ids = ser.validated_data['user_ids']
        _, missing = assign_users_to_job(job, user_ids, request.user)
        job = _job_detail_qs(request.user).get(pk=job.pk)
        payload = {'data': JobDetailSerializer(job).data}
        if missing:
            payload['unassigned_user_ids'] = missing
            payload['message'] = 'Some user IDs were skipped (wrong organization, inactive, or invalid).'
        return Response({'status': 200, **payload}, status=status.HTTP_200_OK)


class JobAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not is_job_manager(request.user):
            return _forbidden_manager()
        assignment = get_object_or_404(
            JobAssignment.objects.select_related('job'),
            pk=pk,
        )
        get_object_or_404(job_queryset_for_user(request.user), pk=assignment.job_id)
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_pk):
        if not is_job_manager(request.user):
            return _forbidden_manager()
        job = get_object_or_404(job_queryset_for_user(request.user), pk=job_pk)
        ser = JobCompleteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            complete_job(job, request.user, ser.validated_data.get('completion_notes', ''))
        except ValueError as e:
            return _bad_request(str(e))
        job = _job_detail_qs(request.user).get(pk=job.pk)
        return Response(
            {'status': 200, 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK,
        )


class JobCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_pk):
        if not is_job_manager(request.user):
            return _forbidden_manager()
        job = get_object_or_404(job_queryset_for_user(request.user), pk=job_pk)
        ser = JobCloseSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        close_job(job, request.user, ser.validated_data.get('closing_notes', ''))
        job = _job_detail_qs(request.user).get(pk=job.pk)
        return Response(
            {'status': 200, 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK,
        )
