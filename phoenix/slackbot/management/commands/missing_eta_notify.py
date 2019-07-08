import logging

from django.core.management.base import BaseCommand

from ...tasks import missing_eta_notify

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Notifies solution assignee after certain ammount of time when ETA is unknown"
    )

    def handle(self, *args, **options):
        missing_eta_notify()
