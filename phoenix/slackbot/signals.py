from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from phoenix.core.models import Monitor, Outage, Solution

from .models import Announcement
from .tasks import create_or_update_announcement, sync_monitor_details_task


@receiver(post_save, sender=Outage)
def outage_changed(sender, instance, created, **kwargs):
    if created:
        Announcement(
            outage=instance, channel_id=settings.SLACK_ANNOUNCE_CHANNEL_ID
        ).save()
    check_history = not instance.resolved  # check history only if not resolved incident
    create_or_update_announcement.delay(
        outage_pk=instance.pk, check_history=check_history
    )


@receiver(post_save, sender=Solution)
def solution_changed(sender, instance, created, **kwargs):
    pk = instance.outage.pk
    create_or_update_announcement.delay(outage_pk=pk, check_history=True)


@receiver(post_save, sender=Monitor)
def monitor_changed(sender, instance, created, **kwargs):
    if created:
        sync_monitor_details_task.delay(instance.id)
