from django.conf import settings
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from phoenix.core.models import Monitor, Outage, Solution, PostmortemNotifications

from .models import Announcement
from .tasks import create_or_update_announcement, sync_monitor_details_task


@receiver(post_save, sender=Outage)
def outage_changed(sender, instance, created, **kwargs):
    if created:
        Announcement(outage=instance, channel_id=settings.SLACK_ANNOUNCE_CHANNEL_ID).save()
    create_or_update_announcement.delay(outage_pk=instance.pk, check_history=True)


@receiver(m2m_changed, sender=Outage.systems_affected.through)
def outage_systems_changed(sender, instance, action, **kwargs):
    if action in ['post_add', 'post_remove']:
        create_or_update_announcement.delay(outage_pk=instance.pk, check_history=True)


@receiver(post_save, sender=Solution)
def solution_changed(sender, instance, created, **kwargs):
    pk = instance.outage.pk
    create_or_update_announcement.delay(outage_pk=pk, check_history=True,
                                        resolved=True)


@receiver(post_save, sender=Monitor)
def monitor_changed(sender, instance, created, **kwargs):
    if created:
        sync_monitor_details_task.delay(instance.id)
