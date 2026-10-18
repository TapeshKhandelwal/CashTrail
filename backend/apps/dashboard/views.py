from collections.abc import Callable
from typing import Any

from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework.generics import ListAPIView
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.schema import error_responses

from . import reports, selectors
from .permissions import IsSupervisor
from .selectors import DashboardFilters
from .serializers import (
    AgentRowSerializer,
    BranchRowSerializer,
    CollectionReportFilterSerializer,
    DashboardFilterSerializer,
    DashboardSummarySerializer,
    DepositReportFilterSerializer,
    DiscrepancyReportFilterSerializer,
    LifecycleSerializer,
    SubmissionReportFilterSerializer,
    TrendFilterSerializer,
    TrendPointSerializer,
)


class FilteredViewMixin:
    filter_serializer_class = DashboardFilterSerializer

    def get_filters(self) -> DashboardFilters:
        serializer = self.filter_serializer_class(
            data=self.request.query_params, context={"request": self.request}
        )
        serializer.is_valid(raise_exception=True)
        return serializer.to_filters()


@extend_schema(
    parameters=[DashboardFilterSerializer],
    responses={200: DashboardSummarySerializer, **error_responses(400)},
)
class DashboardSummaryView(FilteredViewMixin, APIView):
    def get(self, request):
        summary = selectors.dashboard_summary(request.user, self.get_filters())
        return Response(DashboardSummarySerializer(summary).data)


@extend_schema(
    parameters=[TrendFilterSerializer],
    responses={200: TrendPointSerializer(many=True), **error_responses(400)},
)
class DashboardTrendView(FilteredViewMixin, APIView):
    filter_serializer_class = TrendFilterSerializer

    def get(self, request):
        points = selectors.collection_trend(request.user, self.get_filters())
        return Response(TrendPointSerializer(points, many=True).data)


@extend_schema(
    parameters=[DashboardFilterSerializer],
    responses={200: LifecycleSerializer, **error_responses(400)},
)
class DashboardLifecycleView(FilteredViewMixin, APIView):
    def get(self, request):
        lifecycle = selectors.collection_lifecycle(request.user, self.get_filters())
        return Response(LifecycleSerializer(lifecycle).data)


class BreakdownView(FilteredViewMixin, ListAPIView):
    """Paginates the rows (branches or agents) first, then aggregates only that page."""

    permission_classes = [IsSupervisor]
    filter_backends = []
    select_rows: Callable[[Any, DashboardFilters], QuerySet]
    aggregate_rows: Callable[[Any, DashboardFilters, list], list[dict]]

    def list(self, request, *args, **kwargs):
        filters = self.get_filters()
        page = self.paginate_queryset(self.select_rows(request.user, filters))
        rows = self.aggregate_rows(request.user, filters, page)
        return self.get_paginated_response(self.get_serializer(rows, many=True).data)


@extend_schema(
    parameters=[DashboardFilterSerializer],
    responses={200: BranchRowSerializer(many=True), **error_responses(400, 403)},
)
class BranchBreakdownView(BreakdownView):
    serializer_class = BranchRowSerializer
    select_rows = staticmethod(selectors.branches_for_breakdown)
    aggregate_rows = staticmethod(selectors.branch_breakdown)


@extend_schema(
    parameters=[DashboardFilterSerializer],
    responses={200: AgentRowSerializer(many=True), **error_responses(400, 403)},
)
class AgentBreakdownView(BreakdownView):
    serializer_class = AgentRowSerializer
    select_rows = staticmethod(selectors.agents_for_breakdown)
    aggregate_rows = staticmethod(selectors.agent_breakdown)


class JSONErrorNegotiation(BaseContentNegotiation):
    """Report bodies are streamed as CSV directly; anything rendered (errors) is JSON,
    whatever the client's Accept header asks for."""

    def select_parser(self, request, parsers):
        return parsers[0] if parsers else None

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


CSV_RESPONSES = {
    (200, "text/csv"): OpenApiResponse(OpenApiTypes.STR, description="CSV attachment."),
    **error_responses(400, 401, 403),
}


class ReportView(FilteredViewMixin, APIView):
    report: reports.Report
    renderer_classes = [JSONRenderer]
    content_negotiation_class = JSONErrorNegotiation

    def get(self, request):
        filters = self.get_filters()
        rows = self.report.rows(request.user, filters).iterator(chunk_size=2000)
        response = StreamingHttpResponse(
            reports.stream_csv(self.report.columns, rows), content_type="text/csv; charset=utf-8"
        )
        filename = f"{self.report.name}_{filters.date_from}_{filters.date_to}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


def report_schema(report: reports.Report, filter_serializer):
    return extend_schema_view(
        get=extend_schema(
            operation_id=f"reports_{report.name}_csv",
            parameters=[filter_serializer],
            responses=CSV_RESPONSES,
        )
    )


@report_schema(reports.COLLECTIONS, CollectionReportFilterSerializer)
class CollectionsReportView(ReportView):
    report = reports.COLLECTIONS
    filter_serializer_class = CollectionReportFilterSerializer


@report_schema(reports.SUBMISSIONS, SubmissionReportFilterSerializer)
class SubmissionsReportView(ReportView):
    report = reports.SUBMISSIONS
    filter_serializer_class = SubmissionReportFilterSerializer


@report_schema(reports.DEPOSITS, DepositReportFilterSerializer)
class DepositsReportView(ReportView):
    report = reports.DEPOSITS
    filter_serializer_class = DepositReportFilterSerializer
    permission_classes = [IsSupervisor]


@report_schema(reports.DISCREPANCIES, DiscrepancyReportFilterSerializer)
class DiscrepanciesReportView(ReportView):
    report = reports.DISCREPANCIES
    filter_serializer_class = DiscrepancyReportFilterSerializer
