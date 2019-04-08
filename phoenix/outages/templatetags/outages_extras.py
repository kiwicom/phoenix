from django import template
from django.contrib.auth import get_user_model

from ...core.utils import user_can_announnce

register = template.Library()


@register.filter
def can_user_edit_outage(obj, user_id):
    return obj.can_edit_outage(user_id)


@register.filter
def can_user_create_outage(user_id):
    user = get_user_model().objects.get(id=user_id)
    return user_can_announnce(user)
