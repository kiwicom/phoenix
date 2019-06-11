from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import utils

from ....integration.models import GoogleGroup


class Command(BaseCommand):
    help = "Setup general configuration in Phoenix admin"

    def handle(self, *args, **options):
        for group_name, permission in (
            ("on_call", "add_announcement"),
            ("edit_all_outages", "change_outage"),
        ):
            group_permission = Permission.objects.get(codename=permission)
            group, _ = Group.objects.get_or_create(name=group_name)
            group.permissions.set([group_permission])
