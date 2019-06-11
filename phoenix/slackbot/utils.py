import copy
import json
import logging

import dateutil
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from rest_framework.response import Response

from ..core.models import System
from .bot import slack_client

logger = logging.getLogger(__name__)


def transfrom_slack_email_domain(slack_email):
    """Check if mail domain is the allowed domain.

    If not transfrom the email domain to allowed domain.

    This is required in our usecase because some people
    use old email domain in slack. We change the domain to
    allowed domain for users to be matched correctly when
    logging to Web GUI. This works for us because the email
    address format doesn't change accross this domains.
    """
    allowed_domain = settings.ALLOWED_EMAIL_DOMAIN
    logger.info(f"start: {allowed_domain}")
    if not allowed_domain or slack_email.endswith(f"@{allowed_domain}"):
        logger.info("returning without change")
        return slack_email

    email_parts = slack_email.split("@")
    email_parts[1] = allowed_domain
    new_email = "@".join(email_parts)
    logger.warning(f"Email {slack_email} transformed to {new_email}")
    return new_email


def get_absolute_url(rel_url):
    """Return absolute URL according to app configuration."""
    protocol = "http" if settings.DEBUG else "https"
    domain = Site.objects.get_current().domain
    return f"{protocol}://{domain}{rel_url}"


def get_system_option():
    return [
        {"label": system.name, "value": system.id} for system in System.objects.all()
    ]


def format_datetime(timestamp):
    """Return slack formatted datetime."""
    return f"<!date^{int(timestamp)}^{{date_pretty}} at {{time}}| >"


def format_duration(start, end, duration):
    return "{start} - {end} ({duration} min.)".format(
        start=format_datetime(start.timestamp()),
        end=format_datetime(end.timestamp()),
        duration=duration,
    )


def format_user_for_slack(user):
    """Return slack formatted username.

    If user doesn't have last_name set, return unformated email.
    """
    if getattr(user, "last_name", None):
        return f"<@{user.last_name}>"
    return user.email


def retrieve_user(**kwargs):
    user_model = get_user_model()
    try:
        return user_model.objects.get(**kwargs)
    except user_model.DoesNotExist:
        return None


def provision_slack_user(slack_id):
    if not slack_id:
        return None

    user = retrieve_user(last_name=slack_id)
    if not user:
        resp = slack_client.api_call("users.profile.get", user=slack_id)
        if resp["ok"]:
            slack_user_email = resp["profile"]["email"]
            user = retrieve_user(email=slack_user_email)
            if not user:
                # user is a new one
                user = get_user_model().objects.create_user(
                    slack_id, slack_user_email, last_name=slack_id
                )
            else:
                # user exists but we need to set his Slack ID
                user.last_name = slack_id
                user.save()
    return user


def verify_token(fun):
    def decorator(request, *args, **kwargs):
        token = request.data.get("token")
        if token is None and "payload" in request.data:
            token = json.loads(request.data["payload"]).get("token")
        if token != settings.SLACK_VERIFICATION_TOKEN:
            data = {
                "response_type": "ephemeral",
                "text": "Sorry, that didn't work. Failed token verification.",
            }
            return Response(data, 200)
        return fun(request, *args, **kwargs)

    return decorator


def remove_field_from_attachment(attachment, field_name):
    new_attachment = copy.copy(attachment)
    for i, field in enumerate(attachment["fields"]):
        if field["title"] == field_name:
            new_attachment["fields"].pop(i)
            return new_attachment


def format_url_for_slack(url, name):
    return f"<{url}|{name}>"


def join_channels(channels_to_join):
    """Invite slack bot into all channels from list.

    channels_to_join = ['channel-a', 'alerts']
    """
    bot_id = settings.SLACK_BOT_ID
    limit = 200
    cursor = ""
    channels_to_join = set(channels_to_join)

    while True:
        resp = slack_client.api_call(
            "channels.list", exclude_members=True, limit=limit, cursor=cursor
        )

        if "response_metadata" in resp:
            cursor = resp["response_metadata"]["next_cursor"]

        slack_channels = resp["channels"]
        for channel in slack_channels:
            if channel["name"] in channels_to_join:
                channels_to_join.remove(channel["name"])
                channel_id = channel["id"]
                resp = slack_client.api_call(
                    "channels.invite", channel=channel_id, user=bot_id
                )
                if resp.get("ok"):
                    logger.info(f"Bot was invited to channel {channel_id}")

        if cursor == "":
            break

        if not channels_to_join:
            break

    if channels_to_join:
        logger.warning(f"Unable to find slack channels: {channels_to_join}")
    else:
        logger.info("Bot in all required channels.")


def resolved_at_to_utc(user_time, user_tz):
    """Transform time input from user into specified timezone.

    user_time (arrow datetime): user input as arrow datetime object
    user_tz (string/tzfile): timezone used by user
    """
    if isinstance(user_tz, str):
        user_tz = dateutil.tz.gettz(user_tz)

    localized_time = user_time.replace(tzinfo=user_tz)
    return localized_time.to("UTC").datetime


def utc_to_user_time(utc_time, user_tz):
    """Transform UTC time into user localized time."""
    if isinstance(user_tz, str):
        user_tz = dateutil.tz.gettz(user_tz)
    return utc_time.to(user_tz).datetime


def get_slack_channel_name(channel_id):
    resp = slack_client.api_call("channels.info", channel=channel_id)
    if resp["ok"]:
        return resp["channel"]["name"]
    return None
