from datetime import timedelta

from celery.schedules import crontab
from django.apps import AppConfig

from ..core.celery import app as celery_app


class SlackbotConfig(AppConfig):
    name = 'phoenix.slackbot'

    def ready(self):
        import phoenix.slackbot.signals  # pylint: disable=bad-option-value,unused-import

        from .tasks import (join_datadog_channels, notify_users, sync_user_groups_with_google,
                            notify_users_with_due_date_postmortems, generate_after_due_date_issues_report)

        celery_app.add_periodic_task(timedelta(minutes=20), notify_users)
        celery_app.add_periodic_task(timedelta(hours=8), sync_user_groups_with_google)
        celery_app.add_periodic_task(timedelta(hours=24), join_datadog_channels)
        celery_app.add_periodic_task(timedelta(hours=24), notify_users_with_due_date_postmortems)
        celery_app.add_periodic_task(crontab(hour=1, minute=0), generate_after_due_date_issues_report)
