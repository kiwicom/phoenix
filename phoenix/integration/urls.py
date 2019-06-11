from django.conf.urls import url
from rest_framework.urlpatterns import format_suffix_patterns

from .views import handle_pingdom

urlpatterns = [url(r"^pingdom$", handle_pingdom)]

urlpatterns = format_suffix_patterns(urlpatterns)
