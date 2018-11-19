import json
import logging

from rest_framework.authentication import BaseAuthentication

from .utils import provision_slack_user

logger = logging.getLogger(__name__)


class SlackAuthentication(BaseAuthentication):
    def authenticate(self, request):

        slack_user_id = request.data.get('user_id')

        if not slack_user_id and 'payload' in request.data:
            data = json.loads(request.data['payload'])
            slack_user_id = data['user']['id']
        else:
            logger.warning('Unable to retrieve slack user')

        user = provision_slack_user(slack_user_id)
        return (user, None)
