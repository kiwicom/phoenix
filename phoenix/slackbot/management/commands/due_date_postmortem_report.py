import logging

from django.core.management.base import BaseCommand

from ...tasks import generate_after_due_date_issues_report

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Retrieve gitlab issues after due date and create report."""

    def handle(self, *args, **options):
        generate_after_due_date_issues_report()
