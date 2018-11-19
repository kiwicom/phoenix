import logging

from django.core.management.base import BaseCommand

from ...tasks import notify_users_with_due_date_postmortems

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Notifies assignees on gitlab issues that are nearing due date (on configured intervals)'

    def handle(self, *args, **options):
        notify_users_with_due_date_postmortems()
