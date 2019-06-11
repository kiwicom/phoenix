import logging

from django.core.management.base import BaseCommand

from ...tasks import join_datadog_channels

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Joins all slack channels used by datadog to agregate all alerts"

    def handle(self, *args, **options):
        join_datadog_channels()
