# copyright mario.hunka kiwibase

import logging

from django.core.management import BaseCommand

from ...tasks import sync_user_groups_with_google

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Update user groups according to google groups.

    Takes list of users in specified groups and updates
    groups for users in our database.
    """

    help = "Update user groups according to google groups."

    def handle(self, *args, **options):
        sync_user_groups_with_google()
