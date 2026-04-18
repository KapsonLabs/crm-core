from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsJobManager

from . import services


def _bad(message: str):
    return Response({'status': 400, 'message': message}, status=status.HTTP_400_BAD_REQUEST)


def _parse_optional_uuid(s: str | None):
    if not s or not str(s).strip():
        return None
    return str(s)


def _fmt_money(d: Decimal) -> str:
    return f'{d:.2f}'


class AnalyticsTotalsView(APIView):
    permission_classes = [IsAuthenticated, IsJobManager]

    def get(self, request):
        org_raw = request.query_params.get('organization_id')
        branch_raw = request.query_params.get('branch_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        year_raw = request.query_params.get('year')

        if (start_date and not end_date) or (end_date and not start_date):
            return _bad('Provide both start_date and end_date, or neither.')

        year = None
        if year_raw is not None and str(year_raw).strip():
            try:
                year = int(year_raw)
            except (TypeError, ValueError):
                return _bad('Invalid year.')

        try:
            org_id = services.resolve_organization_id(request.user, org_raw)
        except ValueError as e:
            return _bad(str(e))

        branch_id = _parse_optional_uuid(branch_raw)

        try:
            data = services.totals(
                organization_id=org_id,
                branch_id=branch_id,
                start_date=start_date,
                end_date=end_date,
                year=year,
            )
        except ValueError as e:
            return _bad(str(e))

        payload = {
            'total_jobs': data['total_jobs'],
            'revenue': _fmt_money(data['revenue']),
            'expenditure': _fmt_money(data['expenditure']),
            'profit': _fmt_money(data['profit']),
            'period': data['period'],
        }
        return Response({'status': 200, 'data': payload}, status=status.HTTP_200_OK)


class AnalyticsMonthlyRevenueExpenditureView(APIView):
    permission_classes = [IsAuthenticated, IsJobManager]

    def get(self, request):
        org_raw = request.query_params.get('organization_id')
        branch_raw = request.query_params.get('branch_id')
        year_raw = request.query_params.get('year')
        if not year_raw:
            return _bad('year is required.')
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            return _bad('Invalid year.')

        try:
            org_id = services.resolve_organization_id(request.user, org_raw)
        except ValueError as e:
            return _bad(str(e))

        branch_id = _parse_optional_uuid(branch_raw)
        data = services.monthly_revenue_expenditure(
            organization_id=org_id,
            branch_id=branch_id,
            year=year,
        )
        return Response({'status': 200, 'data': data}, status=status.HTTP_200_OK)


class AnalyticsTopSellingView(APIView):
    permission_classes = [IsAuthenticated, IsJobManager]

    def get(self, request):
        org_raw = request.query_params.get('organization_id')
        branch_raw = request.query_params.get('branch_id')
        year_raw = request.query_params.get('year')
        if not year_raw:
            return _bad('year is required.')
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            return _bad('Invalid year.')

        try:
            org_id = services.resolve_organization_id(request.user, org_raw)
        except ValueError as e:
            return _bad(str(e))

        branch_id = _parse_optional_uuid(branch_raw)
        data = services.top_selling(
            organization_id=org_id,
            branch_id=branch_id,
            year=year,
        )
        return Response({'status': 200, 'data': data}, status=status.HTTP_200_OK)


class AnalyticsAverageTimeToServiceView(APIView):
    permission_classes = [IsAuthenticated, IsJobManager]

    def get(self, request):
        org_raw = request.query_params.get('organization_id')
        branch_raw = request.query_params.get('branch_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        year_raw = request.query_params.get('year')

        if (start_date and not end_date) or (end_date and not start_date):
            return _bad('Provide both start_date and end_date, or neither.')

        year = None
        if year_raw is not None and str(year_raw).strip():
            try:
                year = int(year_raw)
            except (TypeError, ValueError):
                return _bad('Invalid year.')

        try:
            org_id = services.resolve_organization_id(request.user, org_raw)
        except ValueError as e:
            return _bad(str(e))

        branch_id = _parse_optional_uuid(branch_raw)

        try:
            data = services.average_time_to_service(
                organization_id=org_id,
                branch_id=branch_id,
                start_date=start_date,
                end_date=end_date,
                year=year,
            )
        except ValueError as e:
            return _bad(str(e))

        payload = {
            'average_seconds': data['average_seconds'],
            'average_days': data['average_days'],
            'sample_size': data['sample_size'],
            'period': data['period'],
        }
        return Response({'status': 200, 'data': payload}, status=status.HTTP_200_OK)
