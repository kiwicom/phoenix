import logging
import re

# Ignore PyImportSortBear
from django.conf import settings
from datadog import api, initialize

from ..core.models import Monitor

logger = logging.getLogger(__name__)

options = {"api_key": settings.DATADOG_API_KEY, "app_key": settings.DATADOG_APP_KEY}

initialize(**options)

RE_FIND_SLACK_CHANNELS = re.compile(r"@slack-([a-z_\-]+)", re.I)


def get_all_slack_channels():
    """Return names of all channels used by datadog monitors."""
    data = api.Monitor.get_all()

    matches = RE_FIND_SLACK_CHANNELS.findall(str(data))
    matches = list(set(matches))

    slack_channels = list(map(lambda match: match.strip("-"), matches))

    return slack_channels


def sync_monitor_details(monitor):
    if monitor.monitoring_system == Monitor.DATADOG:
        monitor_data = api.Monitor.get(monitor.external_id)

        monitor.name = monitor_data.get("name")
        creator = monitor_data.get("creator")
        if creator:
            monitor.created_by = creator.get("email")
        monitor.save()

        logger.info(f"Monitor {monitor.id} updated.")
