from unittest.mock import patch

from django.contrib.auth import get_user_model
import pytest

from phoenix.core.models import Outage
from phoenix.slackbot.tasks import notify_users


@pytest.mark.django_db
@patch("phoenix.slackbot.tasks.slack_bot_client.api_call")
def test_notify_users(mocked_api_call):
    user = get_user_model().objects.create(
        username="unittest", password="unittest", last_name="unittest"
    )
    solution_user = get_user_model().objects.create(
        username="test-assignee", password="test", last_name="test-assignee"
    )
    outage = Outage(
        summary="unittest outage",
        created_by=user,
        communication_assignee=solution_user,
        solution_assignee=user,
        eta="-30",
    )
    outage.save()
    notify_users()
    assert mocked_api_call.call_count == 4, "Two users should have been notified"


@pytest.mark.django_db
@patch("phoenix.slackbot.tasks.slack_bot_client.api_call")
def test_notify_users_eta_zero(mocked_api_call):
    user = get_user_model().objects.create(
        username="unittest", password="unittest", last_name="unittest"
    )
    outage = Outage(
        summary="unittest outage",
        created_by=user,
        communication_assignee=user,
        solution_assignee=user,
        eta="0",
    )
    outage.save()
    notify_users()
    assert mocked_api_call.call_count == 0, "No notification should have gone out"
