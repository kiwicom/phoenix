import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..core.models import Alert, Monitor
from .utils import is_pingdom_recovery

logger = logging.getLogger(__name__)

ALERT_TYPES = {"LOW": Alert.WARNING, "HIGH": Alert.CRITICAL}

PINGDOM_URL = "https://my.pingdom.com/reports/uptime#check="


@api_view(["POST"])
def handle_pingdom(request):
    data = request.data
    logger.debug("Received message from pingdom")
    logger.debug(data)
    if not is_pingdom_recovery(data):
        url = f"https://my.pingdom.com/reports/uptime#check={data['check_id']}"
        monitor, _ = Monitor.objects.get_or_create(
            monitoring_system=Monitor.PINGDOM, external_id=data["check_id"]
        )
        monitor.link = url
        monitor.description = data["description"]
        monitor.name = data["check_name"]
        alert_type = ALERT_TYPES.get(data["importance_level"], Alert.UNDEFINED)
        monitor.add_occurrence(alert_type, data["state_changed_utc_time"])
        monitor.save()

    return Response(status=status.HTTP_200_OK)
