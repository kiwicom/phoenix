import logging

from django.core.management.base import BaseCommand

from ...tasks import postmortem_notifications

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Check for missing postmortems in announcements and send out notifications."""

    def handle(self, *args, **options):
        postmortem_notifications()
