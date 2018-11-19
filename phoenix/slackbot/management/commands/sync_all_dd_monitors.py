import logging

from django.core.management.base import BaseCommand

from ....core.models import Monitor
from ....integration.datadog import sync_monitor_details

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync all datadog monitors missing "creator" and "name" informations.'

    def handle(self, *args, **options):
        monitors = Monitor.objects.filter(
            name=None,
            monitoring_system=Monitor.DATADOG,
        )
        for monitor in monitors:
            sync_monitor_details(monitor)
