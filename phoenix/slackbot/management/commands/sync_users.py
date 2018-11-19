# copyright mario.hunka kiwibase

import logging

from django.core.management import BaseCommand

from ...tasks import sync_users

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """One time command, to get slack_id for all users.

    Its done by using 'users.list' endpoint.

    This was copied from 'employees' update_info_from slack.
    In the future it can be refactored, no need to do that now.
    """

    def handle(self, *args, **options):
        sync_users()
