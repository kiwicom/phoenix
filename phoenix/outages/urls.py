from django.contrib.auth.decorators import permission_required
from django.urls import path

from .views import (
    MonitorDetail, MonitorList, MonitorUpdateView, OutageCreate, OutageDetail, OutagesList, OutageUpdate,
    SolutionCreate, SolutionUpdate
)

urlpatterns = [
    path('', OutagesList.as_view(), name='outages_list'),
    path('monitors', MonitorList.as_view(), name='monitors_list'),
    path(
        'create',
        permission_required(
            'slackbot.add_announcement',
            login_url='/',
        )(OutageCreate.as_view()),
        name='outage_create',
    ),
    path('<int:pk>', OutageDetail.as_view(), name='outage_detail'),
    path('monitors/<int:pk>', MonitorDetail.as_view(), name='monitor_detail'),
    path('<int:pk>/update', OutageUpdate.as_view(), name='outage_update'),
    path('monitors/<int:pk>/update', MonitorUpdateView.as_view(), name='monitor_update'),
    path('<int:pk>/resolve', SolutionCreate.as_view(), name='outage_resolve'),
    path('<int:pk>/edit-solution', SolutionUpdate.as_view(), name='outage_solution_update'),
]
