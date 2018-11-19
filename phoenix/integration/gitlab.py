import datetime
import logging

from django.conf import settings
import gitlab

logger = logging.getLogger(__name__)


def get_api():
    if settings.GITLAB_URL and settings.GITLAB_PRIVATE_TOKEN:
        return gitlab.Gitlab(settings.GITLAB_URL, private_token=settings.GITLAB_PRIVATE_TOKEN)

    logger.info('Skipping gitlab features...')
    return None


def get_due_date_issues(days=None):
    """List issues with specified days before due date."""
    api = get_api()
    if not api:
        return
    if days:
        days = list(map(int, days.split(',')))
    else:
        days = settings.GITLAB_POSTMORTEM_DAYS_TO_NOTIFY
    days = sorted(days, reverse=True)

    opened_issues = api.issues.list(scope='all', state='opened')

    notify = {}
    now = datetime.date.today()

    for open_issue in opened_issues:
        if not open_issue.due_date:
            continue
        due_date = datetime.date.fromisoformat(open_issue.due_date)
        days_remaining = (due_date - now).days
        for day in days:
            if days_remaining == day:
                notify[open_issue.id] = open_issue
    return notify
