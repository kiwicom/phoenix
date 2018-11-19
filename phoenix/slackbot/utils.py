import copy
import json
import logging

import dateutil
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.urls import reverse
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
    logger.info(f'start: {allowed_domain}')
    if not allowed_domain or slack_email.endswith(f'@{allowed_domain}'):
        logger.info('returning without change')
        return slack_email

    email_parts = slack_email.split('@')
    email_parts[1] = allowed_domain
    new_email = '@'.join(email_parts)
    logger.warning(f'Email {slack_email} transformed to {new_email}')
    return new_email


def get_absolute_url(rel_url):
    protocol = 'http' if settings.DEBUG else 'https'
    domain = Site.objects.get_current().domain
    return f'{protocol}://{domain}{rel_url}'


def get_system_option():
    return [{'label': system.name, 'value': system.id} for system in System.objects.all()]


def format_datetime(timestamp):
    return f'<!date^{int(timestamp)}^{{date_pretty}} at {{time}}| >'


def format_duration(start, end, duration):
    return '{start} - {end} ({duration} min.)'.format(
        start=format_datetime(start.timestamp()),
        end=format_datetime(end.timestamp()),
        duration=duration,
    )


def format_user_for_slack(user):
    if getattr(user, 'last_name', None):
        return f'<@{user.last_name}>'
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
        resp = slack_client.api_call('users.profile.get', user=slack_id)
        if resp['ok']:
            slack_user_email = resp['profile']['email']
            user = retrieve_user(email=slack_user_email)
            if not user:
                # user is a new one
                user = get_user_model().objects.create_user(slack_id, slack_user_email, last_name=slack_id)
            else:
                # user exists but we need to set his Slack ID
                user.last_name = slack_id
                user.save()
    return user


def verify_token(fun):
    def decorator(request, *args, **kwargs):
        token = request.data.get('token')
        if token is None and 'payload' in request.data:
            token = json.loads(request.data['payload']).get('token')
        if token != settings.SLACK_VERIFICATION_TOKEN:
            data = {
                'response_type': 'ephemeral',
                'text': 'Sorry, that didn\'t work. Failed token verification.',
                }
            return Response(data, 200)
        return fun(request, *args, **kwargs)

    return decorator


def remove_field_from_attachment(attachment, field_name):
    new_attachment = copy.copy(attachment)
    for i, field in enumerate(attachment['fields']):
        if field['title'] == field_name:
            new_attachment['fields'].pop(i)
            return new_attachment


def format_url_for_slack(url, name):
    return f'<{url}|{name}>'


SLACK_FIELDS = {
    'sales_choice': {
        'title': 'Sales affected',
        'short': True,
    },
    'sales': {
        'title': 'Sales affected details',
    },
    'system_affected': {
        'title': 'System affected',
        'short': False,
    },
    'eta': {
        'title': 'ETA',
        'short': False,
    },
    'communication_assignee': {
        'title': 'Communication assignee',
        'short': True,
    },
    'solution_assignee': {
        'title': 'Solution assignee',
        'short': True,
    },
    'duration': {
        'title': 'Duration',
    },
    'summary': {
        'title': 'Summary',
    },
    'suggested_outcome': {
        'title': 'Suggested outcome',
        'short': True,
    },
    'link': {
        'title': 'Link',
        'short': True,
    },
}

SLACK_ACTIONS = {
    'edit': {
        'name': 'edit',
        'text': 'Edit',
        'type': 'button',
        'value': 'edit',
    },
    'edit_assignees': {
        'name': 'edit_assignees',
        'text': 'Edit Assignees',
        'type': 'button',
        'value': 'edit_assignees',
    },
    'resolve': {
        'name': 'resolve',
        'text': 'Resolve',
        'type': 'button',
        'style': 'primary',
        'value': 'resolve',
    },
    'edit_solution': {
        'name': 'edit_solution',
        'text': 'Edit',
        'type': 'button',
        'value': 'edit_solution',
    },
    'attach_report': {
        'name': 'attach_report',
        'text': 'Attach Report',
        'type': 'button',
        'value': 'attach_report',
    },
    'create_channel': {
        'name': 'create_channel',
        'text': 'Create channel',
        'type': 'button',
        'value': 'create_channel',
    },
    'assign_channel': {
        'name': 'assign_channel',
        'text': 'Assign channel',
        'type': 'button',
        'value': 'assign_channel',
    },
    'edit_duration': {
        'name': 'edit_duration',
        'text': 'Edit Duration',
        'type': 'button',
        'value': 'edit_duration',
    },
}


def slack_field(field_name, value=None):
    field = SLACK_FIELDS[field_name]
    field['value'] = value
    return field


def create_attachment(outage, announcement):  # Ignore RadonBear
    """Generate announacement data for slack API."""
    outage_rel_link = reverse('outage_detail', kwargs={'pk': outage.pk})
    outage_abs_link = get_absolute_url(outage_rel_link)
    color = 'good' if outage.is_resolved else 'danger'
    attachment = {
        'callback_id': outage.id,
        'fallback': 'Required plain-text summary of the attachment.',
        'color': color,
        'title': announcement.outage.summary,
        'title_link': outage_abs_link,
        'attachment_type': 'default',
        'fields': [],
    }
    attachment_menu = {
        'callback_id': outage.id,
        'fallback': 'Outage menu',
        'color': '#0c67f9',
        'text': '*Buttons only usable by creator or assignees*',
        'attachment_type': 'default',
        'actions': [
            SLACK_ACTIONS['edit'],
            SLACK_ACTIONS['edit_assignees'],
            SLACK_ACTIONS['resolve'],
        ],
    }

    solution = outage.is_resolved
    if solution:
        attachment_menu = {
            'callback_id': outage.id,
            'fallback': 'Resolved outage menu',
            'color': '#0c67f9',
            'text': '*Buttons only usable by creator or assignees*',
            'attachment_type': 'default',
            'actions': [
                SLACK_ACTIONS['edit_solution'],
                SLACK_ACTIONS['edit_duration'],
            ],
        }
        if not solution.report_url:
            attachment_menu['actions'].append(
                SLACK_ACTIONS['attach_report'],
            )
        resolver = format_user_for_slack(solution.created_by)
        footer_msg = f'Outage was resolved by {resolver}'
        attachment['footer'] = footer_msg
        attachment['ts'] = solution.resolved_at.timestamp()
        attachment['footer_icon'] = 'https://slack-imgs.com/?c=1&o1=wi32.he32.si&url=https%3A%2F%2Fs3-us-west-2' \
                                    '.amazonaws.com%2Fpd-slack%2Ficons%2Fresolved.png'
        attachment['fields'] = [
            slack_field('summary', value=solution.summary),
            slack_field('sales_choice', value=outage.sales_affected_choice_human),
        ]
        if outage.sales_affected:
            attachment['fields'].append(
                slack_field('sales', value=outage.sales_affected)
            )
        attachment['fields'].extend([
            slack_field('system_affected', value=', '.join(
                [sys.name for sys in outage.systems_affected.all()]) or 'N/A'),
            slack_field('duration', value=format_duration(outage.started_at,
                                                          outage.solution.resolved_at, outage.solution.real_downtime)),
            slack_field('communication_assignee', value=format_user_for_slack(outage.communication_assignee)),
            slack_field('solution_assignee', value=format_user_for_slack(outage.solution_assignee)),
            slack_field('suggested_outcome', value=solution.get_suggested_outcome_display()),
        ])
        if solution.report_url:
            attachment['fields'].append(
                slack_field('link', value=format_url_for_slack(solution.full_report_url, 'Postmortem')),
            )
    else:
        attachment['fields'] = [
            slack_field('sales_choice', value=outage.sales_affected_choice_human),
        ]
        if outage.sales_affected:
            attachment['fields'].append(slack_field('sales', value=outage.sales_affected))
        attachment['fields'].extend([
            slack_field('system_affected', value=', '.join(
                [sys.name for sys in outage.systems_affected.all()]) or 'N/A'),
            slack_field('eta', value='Unknown' if outage.eta_is_unknown else format_datetime(outage.eta_deadline)),
            slack_field('communication_assignee', value=format_user_for_slack(outage.communication_assignee)),
            slack_field('solution_assignee', value=format_user_for_slack(outage.solution_assignee)),
        ])

    attachments = [attachment, attachment_menu]

    if not outage.is_resolved and not outage.announcement.dedicated_channel_id:
        attachment_channel = {
            'callback_id': outage.id,
            'fallback': 'Dedicated channel menu',
            'color': '#0c67f9',
            'text': 'Dedicated channel',
            'attachment_type': 'default',
            'actions': [
                SLACK_ACTIONS['create_channel'],
                SLACK_ACTIONS['assign_channel'],
            ],
        }
        attachments.append(attachment_channel)
    return attachments


def join_channels(channels_to_join):
    """Invite slack bot into all channels from list.

    channels_to_join = ['channel-a', 'alerts']
    """
    bot_id = settings.SLACK_BOT_ID
    limit = 200
    cursor = ''
    channels_to_join = set(channels_to_join)

    while True:
        resp = slack_client.api_call('channels.list', exclude_members=True, limit=limit, cursor=cursor)

        if 'response_metadata' in resp:
            cursor = resp['response_metadata']['next_cursor']

        slack_channels = resp['channels']
        for channel in slack_channels:
            if channel['name'] in channels_to_join:
                channels_to_join.remove(channel['name'])
                channel_id = channel['id']
                resp = slack_client.api_call('channels.invite', channel=channel_id, user=bot_id)
                if resp.get('ok'):
                    logger.info(f'Bot was invited to channel {channel_id}')

        if cursor == '':
            break

        if not channels_to_join:
            break

    if channels_to_join:
        logger.warning(f'Unable to find slack channels: {channels_to_join}')
    else:
        logger.info('Bot in all required channels.')


def resolved_at_to_utc(user_time, user_tz):
    """Transform time input from user into specified timezone.

    user_time (arrow datetime): user input as arrow datetime object
    user_tz (string/tzfile): timezone used by user
    """
    if isinstance(user_tz, str):
        user_tz = dateutil.tz.gettz(user_tz)

    localized_time = user_time.replace(tzinfo=user_tz)
    return localized_time.to('UTC').datetime


def utc_to_user_time(utc_time, user_tz):
    """Transform UTC time into user localized time."""
    if isinstance(user_tz, str):
        user_tz = dateutil.tz.gettz(user_tz)
    return utc_time.to(user_tz).datetime


def get_slack_channel_name(channel_id):
    resp = slack_client.api_call('channels.info', channel=channel_id)
    if resp['ok']:
        return resp['channel']['name']
    return None
