import logging

from django.db import models

from ..core.models import Outage
from .tasks import create_channel

logger = logging.getLogger(__name__)


class Announcement(models.Model):
    outage = models.OneToOneField(Outage, on_delete=models.CASCADE)
    message_ts = models.CharField(null=True, blank=True, max_length=100)
    channel_id = models.CharField(null=False, blank=False, max_length=100)
    create_dedicated_channel = models.BooleanField(default=False)
    dedicated_channel_id = models.CharField(null=True, blank=True, max_length=100)
    permalink = models.CharField(null=True, blank=True, max_length=200)
    date = models.DateTimeField(auto_now_add=True)
    sales_notified = models.BooleanField(default=False, null=True, blank=True)
    b2b_notified = models.BooleanField(default=False, null=True, blank=True)

    def __init__(self, *args, **kwargs):
        super(Announcement, self).__init__(*args, **kwargs)
        self._create_dedicated_channel = self.create_dedicated_channel

    def __str__(self):
        return f"Announcement {self.outage}"

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        super(Announcement, self).save(force_insert, force_update, using, update_fields)
        if self.create_dedicated_channel and not self._create_dedicated_channel:
            self._create_dedicated_channel = self.create_dedicated_channel
            self.create_channel()

    @property
    def dedicated_channel_name(self):
        date = self.outage.created.date().strftime("%y%m%d")
        systems = self.outage.systems_affected_human
        offset = Outage.objects.filter(
            created__day=self.outage.created.date().day,
            pk__lt=self.outage.pk,
            systems_affected=self.outage.systems_affected,
        ).count()
        msg = f"o-{systems}-{date}"
        if offset:
            return msg + f"-{offset+1}"
        return msg

    def create_channel(self):
        if not self.dedicated_channel_id:
            create_channel.delay(self.outage.id, self.dedicated_channel_name)
        else:
            logger.warning(f"Channel for {self} already created.")
