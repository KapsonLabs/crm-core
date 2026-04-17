from django.urls import path

from .views import (
    KpiDraftVersionCreateView,
    KpiExecutionTriggerView,
    KpiSnapshotListView,
    KpiVersionApproveView,
    KpiVersionPublishView,
)

urlpatterns = [
    path("versions/drafts/", KpiDraftVersionCreateView.as_view(), name="engine-draft-version-create"),
    path(
        "kpis/<uuid:kpi_id>/versions/<int:version>/approve/",
        KpiVersionApproveView.as_view(),
        name="engine-version-approve",
    ),
    path(
        "kpis/<uuid:kpi_id>/versions/<int:version>/publish/",
        KpiVersionPublishView.as_view(),
        name="engine-version-publish",
    ),
    path("execute/", KpiExecutionTriggerView.as_view(), name="engine-execute"),
    path("snapshots/", KpiSnapshotListView.as_view(), name="engine-snapshots"),
]
