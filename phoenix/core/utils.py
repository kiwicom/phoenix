import logging
import time

from django.conf import settings
from django.contrib.auth import get_user_model

from .models import Outage

logger = logging.getLogger(__name__)


def execution_time_logger(fun):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = fun(*args, **kwargs)
        end = time.time()
        logger.debug(f'Execution {fun.__name__}: {end-start}')
        return result

    return wrapper


def user_can_modify_outage(user_id, outage_id, allow_resolved=False):
    """Check if user is linked to outage and outage is not resolved."""
    outage = None
    try:
        outage = Outage.objects.get(id=outage_id)
    except Outage.DoesNotExist:
        logger.error(f"Trying to lookup not existing outage: {outage_id}")
        return False

    allow_edit_resolved = allow_resolved if allow_resolved else not outage.is_resolved

    if user_can_edit_all_outages(user_id) or (outage.can_edit_outage(user_id) and allow_edit_resolved):
        return True
    return False


def user_can_edit_all_outages(user_id):
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f'User {user_id} does not exist')
    return user.has_perm('core.change_outage')


def user_can_announnce(user):
    """Check if user object can announce outage."""
    return settings.ALLOW_ALL_TO_NOTIFY or user.has_perm('slackbot.add_announcement')
