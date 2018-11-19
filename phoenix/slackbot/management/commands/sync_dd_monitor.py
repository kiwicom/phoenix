import logging

from django.core.management.base import BaseCommand

from ...tasks import sync_monitor_details_task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync datadog monitor creater and name to Phoenix'

    def add_arguments(self, parser):
        parser.add_argument('monitor_id', type=str)

    def handle(self, *args, **options):
        monitor_id = options['monitor_id']
        sync_monitor_details_task(monitor_id)
