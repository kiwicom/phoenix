import arrow
import pytest

from phoenix.core.models import System
from phoenix.tests.utils import get_outage


@pytest.mark.django_db
def test_outage_is_resolved():
    o = get_outage()
    assert o.is_resolved is False, "is_resolved not working"


@pytest.mark.django_db
def test_outage_eta_deadline():
    o = get_outage()
    o.eta = 17
    created = arrow.get(o.created).shift(minutes=o.eta)
    assert o.eta_deadline == created.timestamp, 'ETA timestamp is wrong'
    assert o.eta_human_deadline == created.datetime, 'ETA datetime is wrong'


@pytest.mark.django_db
def test_not_resolved_on_time():
    o = get_outage()
    o.eta = -10  # ETA in the past
    assert o.resolved_on_time is False, 'Not resolved after deadline should '\
                                        'be False'


@pytest.mark.django_db
def test_resolved_on_time():
    o = get_outage(with_solution=True)
    o.eta = -10
    assert o.resolved_on_time is False, 'Resolved after deadline should be '\
                                        'False'
    o.eta = 10
    assert o.resolved_on_time is True, 'Resolved on time should return True'


@pytest.mark.django_db
def test_add_remove_affected_system():
    o = get_outage()
    new_system = System(name='test system')
    new_system.save()

    assert o.systems_affected.name == 'Unittest-system'

    o.set_system_affected(new_system.id)
    assert o.systems_affected.name == new_system.name


@pytest.mark.django_db
def test_outage_save():
    o = get_outage()
    outage_history = o.history_outage.all()
    assert len(outage_history) == 1, 'Outage history count problem'


@pytest.mark.django_db
def test_solution_real_downtime():
    o = get_outage(with_solution=True)
    start = arrow.get(o.created)
    end = arrow.get(o.solution.resolved_at)
    minutes, _ = divmod((end - start).seconds, 60)
    assert o.solution.real_downtime == minutes, 'Wrong real_downtime value'
