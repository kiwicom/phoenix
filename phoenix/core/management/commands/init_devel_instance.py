import logging
import os

from allauth.socialaccount.models import SocialApp
from django.contrib.auth.models import Group, User  # Ignore PyUnusedCodeBear
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

from ....slackbot.management.commands.sync_user_groups import Command as SyncUserGroupsCommand
from ....slackbot.management.commands.sync_users import Command as SyncUsersCommand
from ...models import System
from .init_instance import Command as InitInstanceCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize development instance with dummy data'

    def handle(self, *args, **options):
        for system in ('All', 'Booking', 'Search'):
            System(name=f'{system}').save()
        user = User.objects.filter(username='root')
        if not user:
            user = User(
                username='root',
                is_superuser=True,
                is_staff=True,
                is_active=True,
                password='pbkdf2_sha256$100000$PGzAKp6cZJ9d$UZs0VOAKy32cY0ete4'
                         'JQVxLuT1RoWZIehhr8s59FGg8=',
            )
            user.save()
        local_domain = 'localhost:8000'
        site = None
        try:
            site = Site.objects.get(domain='example.com')
            site.domain = 'localhost:8000'
            site.name = 'localhost:8000'
            site.save()
        except Site.DoesNotExist:
            site = Site.objects.get(domain=local_domain)

        social_app = SocialApp(
            provider='google',
            name='google',
            client_id=os.getenv('DEVEL_GOOGLE_OAUTH_CLIENT_ID', 'unspecified'),
            secret=os.getenv('DEVEL_GOOGLE_OAUTH_SECRET', 'unspecified'),
        )
        social_app.save()
        social_app.sites.add(site)

        SyncUsersCommand().handle()
        InitInstanceCommand().handle()

        on_call_group = Group.objects.get(name='on_call')
        for user in User.objects.all():
            user.groups.add(on_call_group)
