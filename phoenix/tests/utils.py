from django.contrib.auth import get_user_model

from phoenix.core.models import Outage, Solution, System, RootCause


def get_outage(with_solution=False):
    user = get_user_model().objects.create(username="unittest", password="unittest")
    system = System.objects.create(name="Unittest-system")
    root_cause = RootCause.objects.create(name="Unittest-root-cause")
    outage = Outage(
        summary="unittest outage",
        created_by=user,
        communication_assignee=user,
        solution_assignee=user,
        sales_affected_choice="Y",
        sales_affected="test",
        systems_affected=system,
        resolved=True,
        root_cause=root_cause,
    )
    outage.save()
    if with_solution:
        solution = Solution(outage=outage, created_by=user)
        solution.save()
    return outage
