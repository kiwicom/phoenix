from django.conf.urls import url
from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import (  # Ignore PyImportSortBear
    announce,
    create_channel,
    handle_events,
    handle_interactions,
    handle_status,
    handle_up,
)

urlpatterns = [
    url(r"^announce$", announce),
    url(r"^interaction$", handle_interactions),
    url(r"^events$", handle_events),
    path("create_channel/<int:pk>", create_channel, name="create_channel"),
    url(r"^status$", handle_status),
    url(r"^health$", handle_status),
    url(r"^up$", handle_up),
]

urlpatterns = format_suffix_patterns(urlpatterns)
