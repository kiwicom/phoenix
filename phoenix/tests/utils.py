from django.contrib.auth import get_user_model

from phoenix.core.models import Outage, Solution


def get_outage(with_solution=False):
    user = get_user_model().objects.create(username='unittest',
                                           password='unittest')
    outage = Outage(summary='unittest outage', created_by=user,
                    communication_assignee=user,
                    solution_assignee=user, sales_affected_choice="Y",
                    sales_affected="test")
    outage.save()
    if with_solution:
        solution = Solution(outage=outage, created_by=user)
        solution.save()
    return outage
