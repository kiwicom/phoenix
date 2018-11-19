from unittest.mock import patch

import json
# Ignore PyImportSortBear
# Coala wants box import at the top, Pylint at the end.
from django.conf import settings
from django.contrib.auth import get_user_model
import pytest
from rest_framework.response import Response
import box

from phoenix.slackbot import utils
from phoenix.slackbot.models import Announcement
from phoenix.tests.utils import get_outage


@pytest.mark.django_db
def test_get_absolute_url():
    user = get_user_model().objects.create(username='test', password='test',
                                           email='test@test.com')
    assert utils.format_user_for_slack(user) == 'test@test.com'
    user.last_name = 'test'
    assert utils.format_user_for_slack(user) == '<@test>'


@pytest.mark.django_db
def test_retrieve_user():
    user = get_user_model().objects.create(username='test', password='test',
                                           last_name='test')
    retrieved_user = utils.retrieve_user(last_name='test')
    assert retrieved_user == user


@pytest.mark.django_db
def test_create_or_update_announcement():
    outage = get_outage()
    announcement = Announcement(outage=outage, channel_id='unittest')

    attachment = utils.create_attachment(outage, announcement)
    assert len(attachment[1]['actions']) == 3
    assert attachment[0]['title'] == 'unittest outage'


@pytest.mark.django_db
def test_create_or_update_announcement_resolved():
    outage = get_outage(with_solution=True)
    announcement = Announcement(outage=outage, channel_id='unittest')

    attachment = utils.create_attachment(outage, announcement)[0]
    assert attachment['color'] == 'good'
    assert not attachment.get('actions')


@pytest.mark.django_db
def test_create_or_update_announcement_dedicated_channel_id():
    outage = get_outage()
    announcement = Announcement(outage=outage, channel_id='unittest',
                                dedicated_channel_id='unittest-dedicated')

    attachment = utils.create_attachment(outage, announcement)
    action_names = [action['name'] for action in attachment[1]['actions']]
    assert 'createchannel' not in action_names


def test_verify_token():
    def test_func(*args, **kwargs):
        return args, kwargs
    verify_token_func = utils.verify_token(test_func)
    request = {
        "data": {'token': settings.SLACK_VERIFICATION_TOKEN}
    }
    request = box.Box(request)
    data = verify_token_func(request)
    assert isinstance(data, tuple), "Should have called the wrapped function"

    request.data.token = 'test'
    data = verify_token_func(request)
    assert isinstance(data, Response), "Should have returned error Response"

    request = {
        "data": {
            "payload": json.dumps({
                "token": settings.SLACK_VERIFICATION_TOKEN
            })
        }
    }
    request = box.Box(request)
    data = verify_token_func(request)
    assert isinstance(data, tuple), "Should have called the wrapped function"


@patch('phoenix.slackbot.utils.slack_client.api_call')
def test_join_channels(mocked_api_call):
    mocked_api_call.return_value = {'channels': [
        {'id': '123sd', 'name': 'test-channel'},
        {'id': '45fg', 'name': 'channel-a'},
    ]}
    channels_to_join = ['channel-x', 'test-channel', 'channel-a']
    utils.join_channels(channels_to_join)
    test_called_with = (
        "call('channels.list', cursor='', exclude_members=True, limit=200)",
        "call('channels.invite', channel='123sd', user='unittest-bot-id')",
        "call('channels.invite', channel='45fg', user='unittest-bot-id')",
    )
    for i, args in enumerate(mocked_api_call.call_args_list):
        assert str(args) == test_called_with[i]
