from django import template
from django.contrib.auth import get_user_model

register = template.Library()


@register.filter
def can_user_edit_outage(obj, user_id):
    return obj.can_edit_outage(user_id)


@register.filter
def can_user_create_outage(user_id):
    user = get_user_model().objects.get(id=user_id)
    return user.has_perm('slackbot.add_announcement')
