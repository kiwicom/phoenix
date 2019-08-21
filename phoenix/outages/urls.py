from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.urls import path

from .views import (
    MonitorDetail,  # Ignore PyImportSortBear
    MonitorList,
    MonitorUpdateView,
    OutageCreate,
    OutageDetail,
    OutagesList,
    OutageUpdate,
    SolutionCreate,
    SolutionUpdate,
    reopen_outage,
)

if settings.ALLOW_ALL_TO_NOTIFY:
    create_view = OutageCreate.as_view()
else:
    create_view = permission_required("slackbot.add_announcement", login_url="/")(
        OutageCreate.as_view()
    )

urlpatterns = [
    path("", OutagesList.as_view(), name="outages_list"),
    path("monitors", MonitorList.as_view(), name="monitors_list"),
    path("create", create_view, name="outage_create"),
    path("<int:pk>", OutageDetail.as_view(), name="outage_detail"),
    path("monitors/<int:pk>", MonitorDetail.as_view(), name="monitor_detail"),
    path("<int:pk>/update", OutageUpdate.as_view(), name="outage_update"),
    path(
        "monitors/<int:pk>/update", MonitorUpdateView.as_view(), name="monitor_update"
    ),
    path("<int:pk>/resolve", SolutionCreate.as_view(), name="outage_resolve"),
    path(
        "<int:pk>/edit-solution",
        SolutionUpdate.as_view(),
        name="outage_solution_update",
    ),
    path("<int:pk>/reopen_outage", reopen_outage, name="reopen_outage"),
]
