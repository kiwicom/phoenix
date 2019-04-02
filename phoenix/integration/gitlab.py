import datetime
import logging
import re
from urllib.parse import urlparse

from django.conf import settings
import gitlab

logger = logging.getLogger(__name__)


def get_api():
    if settings.GITLAB_URL and settings.GITLAB_PRIVATE_TOKEN:
        return gitlab.Gitlab(settings.GITLAB_URL, private_token=settings.GITLAB_PRIVATE_TOKEN)

    logger.info('Skipping gitlab features...')
    return None


def postmortem_project():
    api = get_api()
    if not api:
        return
    project = api.projects.get(settings.GITLAB_POSTMORTEM_PROJECT)
    if not project:
        logger.error("Postmortem project not found.")
    return project


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


def parse_report_url(report_url):
    """Parse report url, return project path and issue ID."""
    path = urlparse(report_url).path
    groups = re.match(r'/(?P<group>\w+)/(?P<project>\w+)/issues/(?P<issue_id>\d+)', path)
    if not groups:
        logger.error(f"Report url wrong format: {report_url}")
        logger.debug(f"URL path: {path}")
        return False, False
    project_path = f"{groups['group']}/{groups['project']}"
    return project_path, groups['issue_id']


def get_postmortem_project(api, project_path):
    """Parse project name from URL and get gitlab project."""
    project = api.projects.get(project_path)
    if not project:
        logger.error(f"Unable to retrieve gitlab project: {project_path}")
        return
    return project


def get_postmortem_title(report_url):
    """Get title of postmortem (gitlab issue)."""
    project_path, issue_id = parse_report_url(report_url)
    api = get_api()
    if not all((api, project_path, issue_id)):
        return
    project = get_postmortem_project(api, project_path)
    if not project:
        return

    issue = project.issues.get(issue_id)
    if not issue:
        logger.error(f"Issue #{issue_id} not found in postmortem project.")
    return issue.title
