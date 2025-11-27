from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Organization,
    OrganizationLicense,
    Branch,
    BranchSettings,
    BranchUser,
)
from .serializers import (
    OrganizationSerializer,
    OrganizationLicenseSerializer,
    BranchSerializer,
    BranchSettingsSerializer,
    BranchUserSerializer,
)


# -----------------------------------------------------------------------------
# Organization Views
# -----------------------------------------------------------------------------


class OrganizationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        queryset = Organization.objects.annotate(branch_count=Count("branches")).order_by("name")
        organization_id = self.request.query_params.get("organization_id")
        if organization_id:
            queryset = queryset.filter(id=organization_id)
        return queryset


class OrganizationDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer
    queryset = Organization.objects.all()


# -----------------------------------------------------------------------------
# License Views
# -----------------------------------------------------------------------------


class OrganizationLicenseView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationLicenseSerializer

    def get(self, request, *args, **kwargs):
        organization_id = request.query_params.get("organization_id")
        if not organization_id:
            return Response(
                {"organization_id": "organization_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        license_obj = get_object_or_404(OrganizationLicense, organization__id=organization_id)
        serializer = self.serializer_class(license_obj)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_serializer = self.serializer_class(instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, *args, **kwargs):
        organization_id = request.data.get("organization_id")
        if not organization_id:
            return Response(
                {"organization_id": "organization_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        license_obj = get_object_or_404(OrganizationLicense, organization__id=organization_id)
        serializer = self.serializer_class(
            license_obj,
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_serializer = self.serializer_class(instance)
        return Response(response_serializer.data)


# -----------------------------------------------------------------------------
# Branch Views
# -----------------------------------------------------------------------------


class BranchListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BranchSerializer

    def get_queryset(self):
        queryset = Branch.objects.select_related("organization").all()
        organization_id = self.request.query_params.get("organization_id")
        if organization_id:
            queryset = queryset.filter(organization__id=organization_id)
        return queryset


class BranchDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BranchSerializer
    queryset = Branch.objects.select_related("organization").all()


# -----------------------------------------------------------------------------
# Branch Settings Views
# -----------------------------------------------------------------------------


class BranchSettingsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BranchSettingsSerializer

    def get(self, request, *args, **kwargs):
        branch_id = request.query_params.get("branch_id")
        if not branch_id:
            return Response(
                {"branch_id": "branch_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        settings_obj = get_object_or_404(BranchSettings, branch__id=branch_id)
        serializer = self.serializer_class(settings_obj)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_serializer = self.serializer_class(instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, *args, **kwargs):
        branch_id = request.data.get("branch_id")
        if not branch_id:
            return Response(
                {"branch_id": "branch_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        settings_obj = get_object_or_404(BranchSettings, branch__id=branch_id)
        serializer = self.serializer_class(
            settings_obj,
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        response_serializer = self.serializer_class(instance)
        return Response(response_serializer.data)


# -----------------------------------------------------------------------------
# Branch User Views
# -----------------------------------------------------------------------------

class BranchUserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BranchUserSerializer

    def get_queryset(self):
        queryset = BranchUser.objects.select_related("branch", "branch__organization", "user", "role")
        organization_id = self.request.query_params.get("organization_id")
        branch_id = self.request.query_params.get("branch_id")

        if organization_id:
            queryset = queryset.filter(branch__organization__id=organization_id)
        if branch_id:
            queryset = queryset.filter(branch__id=branch_id)

        return queryset


class BranchUserDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BranchUserSerializer
    queryset = BranchUser.objects.select_related("branch", "branch__organization", "user", "role")

