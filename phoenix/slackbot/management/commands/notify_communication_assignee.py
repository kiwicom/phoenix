import logging

from django.core.management.base import BaseCommand

from ...tasks import notify_communication_assignee

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Notifies communication assignees on ongoing outages"

    def handle(self, *args, **options):
        notify_communication_assignee()
