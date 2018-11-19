import logging

from django.core.management.base import BaseCommand

from ...tasks import notify_users

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Notifies assignees about outages in progress and reaching ETA'

    def handle(self, *args, **options):
        notify_users()
