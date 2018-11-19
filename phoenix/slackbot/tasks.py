import logging
import time

import arrow
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, IntegrityError, transaction

from ..core.models import Monitor, Outage, Profile
from ..integration.datadog import get_all_slack_channels, sync_monitor_details
from ..integration.gitlab import get_due_date_issues
from ..integration.google import get_directory_api
from ..integration.models import GoogleGroup
from ..outages.utils import format_datetime as format_outage_datetime
from .bot import slack_bot_client, slack_client
from .utils import (
    create_attachment, format_datetime, format_user_for_slack, join_channels, retrieve_user,
    transfrom_slack_email_domain
)

logger = logging.getLogger(__name__)


@shared_task
def share_message_to_announcement(announcement_ts, announcement_channel, message_ts, message_channel):
    resp = slack_client.api_call('chat.getPermalink', channel=message_channel, message_ts=message_ts)
    if resp['ok']:
        permalink = resp['permalink']
        add_comment(announcement_ts, announcement_channel, permalink)


def get_outage_slack_permalink(announcement, channel_id, message_ts):
    resp = slack_client.api_call('chat.getPermalink', channel=channel_id, message_ts=message_ts)
    if resp['ok']:
        announcement.permalink = resp['permalink']


@shared_task
def create_channel(outage_id, channel_name=None, channel_id=None, invite_users=None):
    from .models import Announcement

    if not channel_id:
        resp = slack_client.api_call('channels.create', name=channel_name)
        invite_users = invite_users or []
        if resp['ok']:
            channel_id = resp['channel']['id']

    if not channel_name:
        resp = slack_client.api_call('channels.info', channel=channel_id)
        if resp['ok']:
            channel_name = resp['channel']['name']
    if channel_id:
        with transaction.atomic():
            announcement = Announcement.objects.select_for_update().get(outage_id=outage_id)
            announcement.dedicated_channel_id = channel_id
            announcement.save(update_fields=['dedicated_channel_id'])

        comment = f'Dedicated slack channel: <#{channel_id}|{announcement.dedicated_channel_name}>'
        add_comment(announcement.message_ts, announcement.channel_id, comment)

        # invite phoenix bot to channel to monitor conversation
        slack_client.api_call('channels.invite', channel=channel_id, user=settings.SLACK_BOT_ID)

        # update announcement to remove action "create channel"
        create_or_update_announcement(outage_id)

        for user in invite_users:
            resp = slack_client.api_call('channels.invite', channel=channel_id, user=user)
            logger.info(resp)

        return channel_id


def notify_user_with_im(user, message=None, attachments=None):
    data = slack_bot_client.api_call('im.open', user=user)
    if not data['ok']:
        logger.error(f"Opening direct message channel failed: {data}")
        return
    channel_id = data['channel']['id']
    data = slack_bot_client.api_call('chat.postMessage', channel=channel_id,
                                     text=message, as_user=False, attachments=attachments)
    if not data['ok']:
        logger.error(f"Posting direct message failed: {data['error']}")


def notify_assigned(user, outage_link, assignee_type='Solution'):
    message = f'You became {assignee_type} assignee on Outage {outage_link}'
    notify_user_with_im(user, message)


def notify_unassigned(user, outage_link, assignee_type='Solution'):
    message = f'You are no longer the {assignee_type} assignee on Outage {outage_link}'
    notify_user_with_im(user, message)


class OutageComment():  # pylint: disable=too-many-instance-attributes

    def __init__(self, outage, versions, announcement, resolved):
        self.outage = outage
        if len(versions) == 2:
            self.current_version, self.previous_version = versions
        else:
            self.current_version, self.previous_version = versions[0], None
        self.announcement = announcement
        self.slack_comments = []
        self.html_comments = []
        self.resolved = resolved
        if self._is_change:
            self.modified_by = self.current_version.modified_by
        else:
            self.modified_by = self.current_version.created_by

    @property
    def _is_change(self):
        return bool(self.previous_version)

    def generate_comments(self):
        """Generate comments in right order."""
        if self.resolved:
            if self._is_change:
                self.generate_resolved_comments()
            else:
                self.add_was_resolved_comment()
        else:
            if self._is_change:
                self.generate_unresolved_comments()
        if any(self.slack_comments):
            # Always add "modified by" at the end if any comment was added
            self.add_modified_by()

    def generate_unresolved_comments(self):
        self.process_more_info()  # Always add more info as first

        if self._eta_changed():
            self.add_eta_changed()
        if self._assignees_changed():
            self.add_assignees_changed()

        fields = ['sales_affected_choice', 'sales_affected']
        self.add_generic_comments(fields)

    def generate_resolved_comments(self):
        fields = ['summary', 'sales_affected_choice', 'sales_affected', 'suggested_outcome', 'report_url',
                  'started_at', 'resolved_at']
        self.add_generic_comments(fields)

    def compose_comments(self):
        return '\n'.join(self.slack_comments), ' '.join(self.html_comments)

    def post_comments(self, slack_comment, html_comment, icon_url=None, username=None):
        resp = add_comment(
            self.announcement.message_ts,
            self.announcement.channel_id,
            slack_comment,
            icon_url=icon_url,
            username=username,
        )
        if resp['ok']:
            self.outage.add_notification(html_comment, self.modified_by)

    def process(self):
        self.generate_comments()
        slack_comment, html_comment = self.compose_comments()
        self.post_comments(slack_comment, html_comment)

    def add_eta_changed(self):
        comment = 'ETA changed to {deadline} (UTC).'
        slack_eta = format_datetime(self.current_version.eta_deadline)
        html_eta = format_outage_datetime(self.current_version.eta_human_deadline)
        if self.current_version.eta_is_unknown:
            html_eta = slack_eta = 'Unknown'

        self.slack_comments.append(comment.format(
            deadline=slack_eta,
        ))
        self.html_comments.append(comment.format(
            deadline=html_eta,
        ))

    def add_assignees_changed(self):
        comment = ' Solution assignee is {solution_assignee}.'
        comment += ' Communication assignee is {communication_assignee}.'

        self.slack_comments.append(comment.format(
            solution_assignee=format_user_for_slack(self.outage.solution_assignee),
            communication_assignee=format_user_for_slack(self.outage.communication_assignee),
        ))
        self.html_comments.append(comment.format(
            solution_assignee=self.outage.solution_assignee.email,
            communication_assignee=self.outage.communication_assignee.email,
        ))

    def process_more_info(self):
        more_info = self.current_version.change_desc
        if more_info:
            self.post_comments(more_info, more_info,
                               icon_url=self.modified_by.profile.image_48_url,
                               username=self.modified_by.profile.slack_username)

    def add_modified_by(self):
        self.slack_comments.append(f'by {format_user_for_slack(self.modified_by)}')

    def add_suggested_outcome_comment(self):
        value = dict(self.current_version.OUTCOME_CHOICES)[self.current_version.suggested_outcome]
        comment = f'Suggested outcome changed to: {value}.'
        self.slack_comments.append(comment)
        self.html_comments.append(comment)

    def add_resolved_at_comment(self):
        slack_value = format_datetime(self.current_version.resolved_at.timestamp())
        html_value = format_outage_datetime(self.current_version.resolved_at)
        comment = 'Resolved at changed to: {} (UTC).'
        self.slack_comments.append(comment.format(slack_value))
        self.html_comments.append(comment.format(html_value))

    def add_started_at_comment(self):
        slack_value = format_datetime(self.current_version.solution.outage.started_at.timestamp())
        html_value = format_outage_datetime(self.current_version.solution.outage.started_at)
        comment = 'Started at changed to: {} (UTC).'
        self.slack_comments.append(comment.format(slack_value))
        self.html_comments.append(comment.format(html_value))

    def add_sales_affected_choice_comment(self):
        if isinstance(self.current_version, Outage):
            choice = self.current_version
        else:
            choice = self.current_version.outage
        value = choice.sales_affected_choice_human
        comment = f'Sales affected changed to: {value}.'
        self.slack_comments.append(comment)
        self.html_comments.append(comment)

    def add_sales_affected_comment(self):
        if isinstance(self.current_version, Outage):
            value = self.current_version.sales_affected
        else:
            value = self.current_version.outage.sales_affected
        comment = f'Sales affected details changed to: {value}.'
        self.slack_comments.append(comment)
        self.html_comments.append(comment)

    def _eta_changed(self):
        """Hack-FIX for ETA change."""
        eta_unknown_change = not self.current_version.eta_is_unknown == self.previous_version.eta_is_unknown
        eta_change = abs(self.current_version.real_eta_in_minutes - self.previous_version.real_eta_in_minutes) >= 2
        return eta_unknown_change or eta_change

    def _assignees_changed(self):
        """Check if curent and previous assignees differ.

        Notify them in DM.
        """
        outage_link = self.current_version.outage.announcement.permalink
        is_solution_same = self.current_version.solution_assignee.id == self.previous_version.solution_assignee.id
        if not is_solution_same:
            notify_unassigned(self.previous_version.solution_assignee.last_name, outage_link)
            notify_assigned(self.current_version.solution_assignee.last_name, outage_link)
        is_communication_same = (self.current_version.communication_assignee.id ==
                                 self.previous_version.communication_assignee.id)
        if not is_communication_same:
            notify_unassigned(self.previous_version.communication_assignee.last_name, outage_link,
                              assignee_type='Communication')
            notify_assigned(self.current_version.communication_assignee.last_name, outage_link,
                            assignee_type='Communication')
        return not all((is_solution_same, is_communication_same))

    def _resolved_at_changed(self):
        return abs(self.current_version.resolved_at.minute - self.previous_version.resolved_at.minute) >= 2

    def _started_at_changed(self):
        outage = self.current_version.solution.outage
        current, previous = outage.history_outage.all()[:2]
        return abs(current.started_at.minute - previous.started_at.minute) >= 2

    def add_generic_comments(self, fields):
        for field in fields:
            changed = False
            current = getattr(self.current_version, field, None)
            previous = getattr(self.previous_version, field, None)
            changed_func = getattr(self, f'_{field}_changed', None)
            if changed_func:
                if changed_func():
                    changed = True
            elif current != previous:
                changed = True
            logger.info(f'{current} - {previous}')
            logger.info(changed)
            if changed:
                custom_comment = getattr(self, f'add_{field}_comment', None)
                if custom_comment:
                    custom_comment()
                else:
                    field_label = ' '.join([f.title() for f in field.split('_')])
                    comment = f'{field_label} changed to: {current}.'
                    self.slack_comments.append(comment)
                    self.html_comments.append(comment)

    def add_was_resolved_comment(self):
        comment = 'Outage has been resolved.'
        self.slack_comments.append(comment)
        self.html_comments.append(comment)


@shared_task  # Ignore RadonBear
def create_or_update_announcement(outage_pk, check_history=False, resolved=False):
    """Core task that updates announcement."""
    from .models import Announcement

    # retrieve outage
    try:
        with transaction.atomic():
            outage = Outage.objects.select_for_update().get(pk=outage_pk)
            announcement = Announcement.objects.select_for_update().get(outage_id=outage.id)

            message_ts = announcement.message_ts
            channel_id = announcement.channel_id
            create_new = message_ts is None
            method = 'chat.postMessage' if create_new else 'chat.update'
            solution = outage.is_resolved

            attachments = create_attachment(outage, announcement)

            resp = slack_client.api_call(
                method,
                channel=channel_id,
                ts=message_ts,
                attachments=attachments,
            )
            if announcement.message_ts is None and resp['ok']:
                announcement.message_ts = resp['ts']
                get_outage_slack_permalink(announcement, channel_id, announcement.message_ts)
                announcement.save()

        if create_new:
            notify_assigned(outage.solution_assignee.last_name, announcement.permalink)
            notify_assigned(outage.communication_assignee.last_name, announcement.permalink,
                            assignee_type='Communication')

        if not solution and method == 'chat.postMessage':
            pin_message(channel_id, announcement.message_ts)
        elif check_history:
            # check history
            if resolved:
                versions = outage.solution.solution_history.all()[:2]
            else:
                versions = outage.history_outage.all()[:2]
            outage_comment = OutageComment(outage, versions, announcement,
                                           resolved)
            outage_comment.process()

        if solution:
            unpin_message(channel_id, announcement.message_ts)
    except DatabaseError:
        logger.warning('Unable to get lock for row')


@shared_task
def post_warning_to_user(user_id, text):
    """Post ephemeral warning message to user."""
    slack_client.api_call(
            method='chat.postEphemeral',
            channel=settings.SLACK_ANNOUNCE_CHANNEL_ID,
            user=user_id,
            text=text,
    )


@shared_task
def pin_message(channel_id, message_ts):
    slack_bot_client.api_call('pins.add', channel=channel_id, timestamp=message_ts)


@shared_task
def unpin_message(channel_id, message_ts):
    slack_bot_client.api_call('pins.remove', channel=channel_id, timestamp=message_ts)


@shared_task
def add_comment(message_ts, channel_id, comment, icon_url=None, username=None):
    resp = slack_client.api_call(
        'chat.postMessage',
        channel=channel_id,
        thread_ts=message_ts,
        text=comment,
        unfurl_links=True,
        as_user=False,
        icon_url=icon_url,
        username=username,
    )
    return resp


@shared_task
def notify_users():
    now = arrow.utcnow().shift(minutes=settings.NOTIFY_BEFORE_ETA)
    for outage in Outage.objects.filter(solution__isnull=True).exclude(eta=0):
        # notify only if eta is known (eta=0 => unknown)
        if arrow.get(outage.eta_deadline) < now:
            announcement = outage.announcement
            assignees = [outage.created_by, outage.solution_assignee, outage.communication_assignee]
            notified = []
            for assignee in assignees:
                user_slack_id = assignee.last_name
                if not user_slack_id:
                    logger.warning(f'Unable to send notification to user {assignee.email} '
                                   f'because slack id is unknown')
                    continue

                if user_slack_id in notified:
                    continue
                formated_eta = format_datetime(outage.eta_deadline)
                notify_user_with_im(user_slack_id, attachments=[
                                              {
                                                  'callback_id': outage.id,
                                                  'fallback': f'Outage {outage.id} not resolved. ETA: {formated_eta}',
                                                  'color': 'danger',
                                                  'title': 'Notification: Outage not resolved',
                                                  'title_link': announcement.permalink,
                                                  'text': outage.summary,
                                                  'fields': [
                                                      {
                                                          'title': 'ETA',
                                                          'value': formated_eta,
                                                          'short': False
                                                          },
                                                      ]
                                                  }
                                              ])
                notified.append(user_slack_id)
                logger.info(f'User {assignee.email} notified.')


def update_or_create_user(kwargs):
    user_model = kwargs['user_model']
    try:
        user = user_model.objects.get(email=kwargs['kiwibase_email'])
        if user.last_name != kwargs['slack_id']:
            user.last_name = kwargs['slack_id']
            user.save()
        if hasattr(user, 'profile'):
            user.profile.timezone = kwargs['slack_timezone']
            user.profile.image_48_url = kwargs['slack_image_48_url']
            user.profile.slack_username = kwargs['slack_username']
            user.profile.save()
        else:
            profile = Profile(user=user, timezone=kwargs['slack_timezone'],
                              image_48_url=kwargs['slack_image_48_url'],
                              slack_username=kwargs['slack_username'])
            profile.save()
    except user_model.DoesNotExist:
        try:
            user = user_model.objects.create_user(
                username=kwargs['slack_id'],
                email=kwargs['kiwibase_email'],
                last_name=kwargs['slack_id'],
            )
        except IntegrityError:
            logger.error(
                f'User with slack ID {kwargs["slack_id"]} has changed email.'
            )
            return
        profile = Profile(user=user, timezone=kwargs['slack_timezone'],
                          image_48_url=kwargs['slack_image_48_url'],
                          slack_username=kwargs['slack_username'])
        profile.save()
        logger.info(f'Created {user}')


@shared_task  # Ignore RadonBear
def sync_users():
    logger.info("Starting script for getting info about employees.")
    cursor = ""
    LIMIT = 200
    count = 1
    logger.info("LIMIT for users.lists %s", LIMIT)

    kwargs = {'user_model': get_user_model()}

    failures = 0

    # get all slack members
    while True:
        logger.debug('Getting %s. list of %s employees', count, LIMIT)
        response = slack_client.api_call("users.list", limit=LIMIT, cursor=cursor)

        # check limited api calls and sleep for a while
        if not response['ok']:
            failures += 1
            if failures == 5:
                logger.warning('Failed %s times. Exiting...', failures)
                break
            logger.info('Bad response %s. Sleeping 20sec... - Failures: %s', response, failures)
            time.sleep(20)
            continue

        logger.debug('Response %s. OK', count)
        # parse user info to user profile+id
        for member in response['members']:
            new_profile = dict()

            if member['is_bot']:
                logger.info('Got bot %s', member['profile'])
                continue

            try:
                kwargs['slack_id'] = member['id']
                kwargs['slack_email'] = member['profile']['email']
                kwargs['slack_timezone'] = member['tz']
                kwargs['slack_image_48_url'] = member['profile']['image_48']
                kwargs['slack_username'] = member['profile']['display_name']
                if not kwargs['slack_username']:
                    kwargs['slack_username'] = member['profile']['real_name']
            except KeyError as e:
                cause = e.args[0]
                logger.info("missing %s - %s", cause, member)
                continue
            new_profile['email'] = kwargs['slack_email']
            if 'skypicker' in kwargs['slack_email']:
                logger.info(kwargs['slack_email'])
            kiwibase_email = transfrom_slack_email_domain(kwargs['slack_email'])
            if not kiwibase_email:
                continue
            kwargs['kiwibase_email'] = kiwibase_email

            update_or_create_user(kwargs)

        if 'response_metadata' in response:
            cursor = response['response_metadata']['next_cursor']
            count += 1
        else:
            cursor = ""

        if cursor == "":
            break


@shared_task
def join_datadog_channels():
    """Invite slack bot into datadog channels."""
    datadog_slack_channels = get_all_slack_channels()
    join_channels(datadog_slack_channels)


@shared_task
def sync_monitor_details_task(monitor_id):
    monitor = Monitor.objects.get(id=monitor_id)
    sync_monitor_details(monitor)


@shared_task
def sync_user_groups_with_google():
    if not settings.GOOGLE_SERVICE_ACCOUNT:
        logger.info('GOOGLE_SERVICE_ACCOUNT not configured skipping...')
        return
    directory_api = get_directory_api()
    google_groups = GoogleGroup.objects.filter(is_allowed=True)

    group = Group.objects.get(name='on_call')

    for google_group in google_groups:
        next_page_token = None
        while True:
            response = directory_api.members().list(
                groupKey=google_group.key,
                pageToken=next_page_token,
            ).execute()
            members = response['members']

            for member in members:
                email = member['email']

                user_model = get_user_model()
                try:
                    user = user_model.objects.get(email=email)
                    user.groups.add(group)
                except user_model.DoesNotExist:
                    logger.warning(f"User {email} is not in phoenix database")

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break


@shared_task
def notify_users_with_due_date_postmortems():
    logger.info('Starting: notify_users_with_due_date_postmortems')
    if not settings.GITLAB_PRIVATE_TOKEN:
        logger.warning('No gitlab private token. Skipping postmortem notifications')
        return
    if not settings.ALLOWED_EMAIL_DOMAIN:
        logger.warning('Only usable with ALLOWED_EMAIL_DOMAIN option set')
        return
    email_domain = settings.ALLOWED_EMAIL_DOMAIN
    due_date_issues = get_due_date_issues()
    for issue in due_date_issues.values():
        url = issue.web_url
        for assignee in issue.assignees:
            # TODO: linking users to slack users using gitlab_api.user.emails.list(). Needs to be admin.
            user = f'{assignee["username"]}@{email_domain}'
            user = retrieve_user(email=user)
            notify_user_with_im(
                user.last_name,
                message=f'Opened postmortem is nearing due date. Please review it. {url}',
            )


@shared_task(time_limit=5)
def test_task():
    return "Pong"
