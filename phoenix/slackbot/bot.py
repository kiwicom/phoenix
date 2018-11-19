import logging

from django.conf import settings
from slackclient import SlackClient

from ..core.utils import execution_time_logger

logger = logging.getLogger(__name__)


class PhoenixSlackClient:
    def __init__(self, token):
        self._slack_client = SlackClient(token)

    # used for debug, sometimes trigger_id expires and it was caused by slow connection...
    @execution_time_logger
    def api_call(self, *args, **kwargs):
        resp = self._slack_client.api_call(*args, **kwargs)

        # if call fails, log error response
        if not resp['ok']:
            method = kwargs.get('method')
            if not method:
                method = args[0]
            logger.error(f'Api call {method} failed. Reason: {resp}')

        return resp


slack_client = PhoenixSlackClient(settings.SLACK_TOKEN)
slack_bot_client = PhoenixSlackClient(settings.SLACK_BOT_TOKEN)
