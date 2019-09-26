from django.contrib import admin

from ..integration.models import GoogleGroup, StatusPageComponent
from .models import Alert, Monitor, Outage, OutageHistory, Solution, System, RootCause

admin.site.register(Outage)
admin.site.register(Solution)
admin.site.register(OutageHistory)
admin.site.register(System)
admin.site.register(RootCause)
admin.site.register(Alert)
admin.site.register(Monitor)
admin.site.register(GoogleGroup)
admin.site.register(StatusPageComponent)
