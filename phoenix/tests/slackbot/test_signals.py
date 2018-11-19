from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist
import pytest

from phoenix.core.models import System
from phoenix.slackbot.models import Announcement
from phoenix.tests.utils import get_outage


@pytest.mark.django_db
@patch('phoenix.slackbot.signals.create_or_update_announcement.delay')
def test_outage_changed(mocked_delay):
    outage = get_outage()
    try:
        Announcement.objects.get(pk=outage.pk)
    except ObjectDoesNotExist:
        pytest.fail("Announcement should have been created")
    assert mocked_delay.call_count == 1  # called after creation

    outage.eta = 15
    outage.save()
    assert mocked_delay.call_count == 2  # called after change


@pytest.mark.django_db
@patch('phoenix.slackbot.signals.create_or_update_announcement.delay')
def test_outage_systems_changed(mock_delay):
    outage = get_outage()
    assert mock_delay.call_count == 1  # called by outage_changed after creation

    system = System(name='test')
    system.save()
    outage.add_affected_system(system.id)
    assert mock_delay.call_count == 2  # called after adding system

    outage.remove_affected_system(system.id)
    assert mock_delay.call_count == 3  # called after removing system


@pytest.mark.django_db
@patch('phoenix.slackbot.signals.create_or_update_announcement.delay')
def test_solution_changed(mock_delay):
    get_outage(with_solution=True)
    assert mock_delay.call_count == 2  # called after outage creation and then
    # after adding solution
