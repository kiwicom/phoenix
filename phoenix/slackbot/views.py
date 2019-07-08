import json
import logging
import re

import arrow
import dateutil
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connections
from django.db.utils import OperationalError
from django.utils import timezone
import kombu
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser
from rest_framework.response import Response

from ..core.models import (  # Ignore PyImportSortBear
    Alert,
    Monitor,
    Outage,
    PostmortemNotifications,
    Profile,
    Solution,
)
from ..core.utils import (
    user_can_announnce,
    user_can_edit_all_outages,
    user_can_modify_outage,
)
from ..integration.gitlab import get_postmortem_title
from .bot import slack_bot_client, slack_client
from .models import Announcement
from .tasks import create_channel as create_channel_task
from .tasks import post_warning_to_user, share_message_to_announcement, test_task
from .utils import (
    get_slack_channel_name,
    get_system_option,
    provision_slack_user,
    resolved_at_to_utc,
    retrieve_user,
    utc_to_user_time,
    verify_token,
)

logger = logging.getLogger(__name__)

callback_pattern = re.compile(r"^([a-z0-9]+)_([a-z]+)$", re.IGNORECASE)
datadog_alert_link_pattern = re.compile(
    r"^(https?://app.datadoghq.com/monitors#(\d+))\?to_ts=(\d+)\&.*$"
)
# https://app.datadoghq.com/monitors#5349493?to_ts=1529939223000&from_ts=1529935623000

OUTCOME_OPT = [
    {"value": option[0], "label": option[1]} for option in Solution.OUTCOME_CHOICES
]
SALES_AFFECTED_CHOICE_OPT = [
    {"value": option[0], "label": option[1]} for option in Outage.SALES_AFFECTED_CHOICES
]
SALES_AFFECTED_CHOICE_OPT_SOLUTION = [
    option for option in SALES_AFFECTED_CHOICE_OPT if option["value"] != Outage.UNKNOWN
]
CHECKBOX_OPT = [{"value": 1, "label": "Yes"}, {"value": 0, "label": "No"}]


def get_handler(event_type):
    handler_name = f"handle_{event_type}"
    handler = globals().get(handler_name)
    if handler is not None:
        return handler

    logger.warning(f"No handler for action: {event_type}")
    return None


@api_view(["GET"])
def handle_status(request):
    return Response(status=status.HTTP_200_OK)


@api_view(["GET"])
def handle_up(request):
    """Check status of required services."""
    db_conn = connections["default"]
    try:
        db_conn.cursor()
    except OperationalError:
        logger.error("Database connection check failed")
        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    data = slack_client.api_call("api.test")
    bot_data = slack_bot_client.api_call("api.test")
    if not data["ok"] or not bot_data["ok"]:
        logger.error("Slack API connection check failed")
        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        test_task.delay()
    except kombu.exceptions.OperationalError:
        logger.error("Celery tasks check failed")
        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
def create_channel(request, pk):
    user = request.get("user")
    if user:
        user_id = user.get("id")
        if user_id:
            if not user_can_modify_outage(user_id, pk):
                post_warning_to_user(
                    user_id=user_id,
                    text="*Buttons only usable by creator or assignees*",
                )
                return Response(status=status.HTTP_200_OK)
    announcement = Announcement.objects.get(outage_id=pk)
    if not announcement.dedicated_channel_id:
        channel_id = create_channel_task(
            announcement.outage.id, announcement.dedicated_channel_name
        )
        data = {"id": channel_id, "name": announcement.dedicated_channel_name}
        return Response(data=data, status=status.HTTP_200_OK)
    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
@verify_token
def handle_events(request):
    data = request.data

    event_type = data["type"]

    handler = get_handler(event_type)
    if handler is not None:
        result = handler(request, data)
        if isinstance(result, Response):
            return result

    return Response(status=status.HTTP_200_OK)


def handle_event_callback(request, data):
    event_type = data["event"]["type"]

    handler = get_handler(event_type)
    if handler is not None:
        result = handler(request, data)
        if isinstance(result, Response):
            return result

    return Response(status=status.HTTP_200_OK)


def _determine_alert_type(title):
    if title.startswith("Triggered"):
        alert_type = Alert.CRITICAL
    elif title.startswith("Warn"):
        alert_type = Alert.WARNING
    else:
        alert_type = Alert.UNDEFINED

    return alert_type


def handle_message(request, data):
    data = data["event"]
    logger.debug("Message arrived")
    logger.debug(str(data))
    # TODO: compare bot_id with Datadog bot ID
    if (
        data.get("bot_id")
        and data.get("subtype") == "bot_message"
        and "attachments" in data
    ):
        m = datadog_alert_link_pattern.match(
            data["attachments"][0].get("title_link", "")
        )
        title = data.get("attachments")[0].get("title", "")
        if m and not title.startswith("Recovered"):
            alert_type = _determine_alert_type(title)
            monitor_link = m.group(1)
            monitor_id = m.group(2)
            alert_ts = arrow.get(
                m.group(3)[:-3]
            ).datetime  # delete zero suffix for miliseconds
            monitor, _ = Monitor.objects.get_or_create(
                external_id=monitor_id,
                defaults={"link": monitor_link},
                monitoring_system=Monitor.DATADOG,
            )
            channel_id = data["channel"]
            if channel_id:
                if monitor.slack_channel_id != channel_id:
                    monitor.slack_channel_id = channel_id
                    monitor.slack_channel_name = get_slack_channel_name(channel_id)
                    monitor.save()
            monitor.add_occurrence(alert_type, alert_ts)

    return Response(status=status.HTTP_200_OK)


def handle_reaction_added(request, data):
    data = data["event"]
    reaction = data["reaction"]
    if reaction != settings.SLACK_EMOJI:
        return

    channel_id = data["item"]["channel"]
    message_ts = data["item"]["ts"]
    # get announcement message to start thread under it
    corresponding_announcement = Announcement.objects.get(
        dedicated_channel_id=channel_id
    )
    if corresponding_announcement.message_ts:
        share_message_to_announcement.delay(
            corresponding_announcement.message_ts,
            corresponding_announcement.channel_id,
            message_ts,
            channel_id,
        )
    else:
        logger.warning("Unable to share message to announcement.")


def handle_team_join(request, data):
    """Save every new member in slack workspace to database."""
    data = data["event"]
    user_data = data["user"]
    if user_data["is_bot"]:
        # Do not save bot users
        logger.debug("Skipping bot user in team_join handler")
        return
    user_slack_id = user_data["id"]
    user_email = user_data["profile"]["email"]
    user_timezone = user_data["tz"]
    image_48_url = user_data["profile"]["image_48"]
    slack_username = user_data["profile"]["display_name"]
    if not slack_username:
        slack_username = user_data["profile"]["real_name"]

    user = retrieve_user(email=user_email)
    if user is None:
        retrieve_user(last_name=user_slack_id)

    if user is None:
        user = get_user_model().objects.create_user(
            user_slack_id, user_email, last_name=user_slack_id
        )
        profile = Profile(
            user=user,
            timezone=user_timezone,
            image_48_url=image_48_url,
            slack_username=slack_username,
        )
        profile.save()
    else:
        user.last_name = user_slack_id
        user.profile.timezone = user_timezone
        user.profile.image_48_url = image_48_url
        user.profile.slack_username = slack_username
        user.profile.save()
        user.save()


def handle_url_verification(request, data):
    challenge = data["challenge"]
    return Response(data={"challenge": challenge}, status=status.HTTP_200_OK)


def handle_user_change(request, data):
    """Handle user changing profile data."""
    user_data = data["event"]["user"]
    if user_data["is_bot"]:
        return

    logger.debug(f"User data: {user_data}")
    user_slack_id = user_data["id"]
    slack_timezone = user_data["tz"]
    image_48_url = user_data["profile"]["image_48"]
    slack_username = user_data["profile"]["display_name"]
    if not slack_username:
        slack_username = user_data["profile"]["real_name"]
    user = retrieve_user(last_name=user_slack_id)
    if user:
        user.profile.timezone = slack_timezone
        user.profile.image_48_url = image_48_url
        user.slack_username = slack_username
        user.profile.save()


@api_view(["GET", "POST"])
@verify_token
def announce(request):
    """Start slack dialog."""
    if not user_can_announnce(request.user):
        logger.warning(f"User {request.user.email} missing permissions")
        post_warning_to_user(
            user_id=request.user.last_name,
            text="*You don't have permissions to use /announce command*",
        )
        return Response(status=status.HTTP_200_OK)
    data = request.data
    logger.debug(data)
    trigger_id = data.get("trigger_id")

    slack_client.api_call(
        "dialog.open",
        trigger_id=trigger_id,
        dialog={
            "callback_id": "outage_new",
            "title": "Announce an outage",
            "submit_label": "Announce",
            "notify_on_cancel": True,
            "elements": [
                {
                    "label": "What happened?",
                    "name": "summary",
                    "type": "textarea",
                    "hint": "Provide outage description.",
                },
                {
                    "label": "Sales affected",
                    "type": "select",
                    "options": SALES_AFFECTED_CHOICE_OPT,
                    "name": "sales_affected_choice",
                    "hint": """If sales have been affected choose Postmortem report
                                                  in Suggested outcome.""",
                },
                {
                    "label": "Lost bookings",
                    "type": "text",
                    "name": "lost_bookings",
                    "subtype": "number",
                    "optional": True,
                    "hint": "Specify how many bookings have been lost if any (e.g. 100).",
                },
                {
                    "label": "Impact on turnover",
                    "type": "text",
                    "name": "impact_on_turnover",
                    "subtype": "number",
                    "optional": True,
                    "hint": "Specify impact on turnover in EUR, if any (e.g. 1000).",
                },
                {
                    "label": "Primary affected system",
                    "type": "select",
                    "name": "affected_system",
                    "options": get_system_option(sort_by=data["text"]),
                    "hint": "Select primary affected system.",
                },
                {
                    "type": "text",
                    "label": "ETA",
                    "name": "eta",
                    "subtype": "number",
                    "hint": "ETA in minutes. Leave empty if unknown.",
                    "optional": True,
                },
            ],
        },
    )

    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
@verify_token
@parser_classes((FormParser,))
def handle_interactions(request):
    """Process slack interactions."""
    data = request.data
    payload = json.loads(data.get("payload"))
    action_type = payload.get("type")

    handler = get_handler(action_type)
    if handler is not None:
        result = handler(request, payload)
        if isinstance(result, Response):
            return result

    return Response(status=status.HTTP_200_OK)


class InteractiveMesssageHandler:
    def __init__(self, request, payload):
        self.action = payload.get("actions")[0]
        self.outage = Outage.objects.get(id=payload.get("callback_id"))
        self.actor_id = payload["user"]["id"]
        self.actor = provision_slack_user(self.actor_id)
        self.trigger_id = payload.get("trigger_id")
        self.user_tz = dateutil.tz.gettz(request.user.profile.timezone)
        self.payload = payload

    def handle(self):
        if not user_can_edit_all_outages(
            self.actor.id
        ) and not self.outage.can_edit_outage(self.actor.id):
            # Check if user can edit outage
            post_warning_to_user(
                user_id=self.actor_id,
                text="*Buttons only usable by creator or assignees*",
            )
            return

        handler = getattr(self, self.action.get("name"), None)
        if handler:
            api_dialog = handler()
            if api_dialog:
                self.slack_api_call(api_dialog)

    def slack_api_call(self, dialog):
        slack_client.api_call("dialog.open", trigger_id=self.trigger_id, dialog=dialog)

    def edit(self):
        return {
            "callback_id": f"{self.outage.id}_edit",
            "title": f"Update outage {self.outage.id}",
            "submit_label": "Update",
            "notify_on_cancel": True,
            "elements": [
                {
                    "type": "text",
                    "label": "ETA",
                    "name": "eta",
                    "subtype": "number",
                    "value": self.outage.eta_remaining,
                    "hint": "ETA in minutes. Leave empty if unknown.",
                    "optional": True,
                },
                {
                    "label": "Sales affected",
                    "type": "select",
                    "options": SALES_AFFECTED_CHOICE_OPT,
                    "name": "sales_affected_choice",
                    "value": self.outage.sales_affected_choice,
                    "hint": "If sales have been affected choose Postmortem report in Suggested outcome.",
                },
                {
                    "label": "Lost bookings",
                    "type": "text",
                    "name": "lost_bookings",
                    "subtype": "number",
                    "optional": True,
                    "value": self.outage.lost_bookings,
                    "hint": "Specify how many bookings have been lost if any (e.g. 100).",
                },
                {
                    "label": "Impact on turnover",
                    "type": "text",
                    "name": "impact_on_turnover",
                    "subtype": "number",
                    "optional": True,
                    "value": self.outage.impact_on_turnover,
                    "hint": "Specify impact on turnover in EUR, if any (e.g. 1000).",
                },
                {
                    "label": "Reason for this change?",
                    "name": "more_info",
                    "type": "textarea",
                    "hint": "State the reason for the change.",
                },
            ],
        }

    def edit_assignees(self):
        return {
            "callback_id": f"{self.outage.id}_editassignees",
            "title": f"Update assignees",
            "submit_label": "Update",
            "notify_on_cancel": True,
            "elements": [
                {
                    "type": "select",
                    "label": "Communication assignee",
                    "name": "communication_assignee",
                    "data_source": "users",
                    "value": self.outage.communication_assignee.last_name,
                },
                {
                    "type": "select",
                    "label": "Solution assignee",
                    "name": "solution_assignee",
                    "data_source": "users",
                    "value": self.outage.solution_assignee.last_name,
                },
            ],
        }

    def resolve(self):
        pn = PostmortemNotifications()
        pn.save()
        # Mark outage as resolved
        self.outage.resolved = True
        self.outage.save()

        if not hasattr(self.outage, "solution"):
            Solution.objects.create(
                outage=self.outage,
                created_by=provision_slack_user(self.actor_id),
                postmortem_notifications=pn,
            )
        else:
            self.outage.solution.save(modified_by=self.actor)
        if not self.outage.sales_affected_choice == Outage.UNKNOWN:
            sales_affected = self.outage.sales_affected_choice
        else:
            sales_affected = ""

        return {
            "callback_id": f"{self.outage.id}_resolve",
            "title": f"{self.outage.summary[:20]}...",
            "submit_label": "Resolve",
            "notify_on_cancel": True,
            "elements": [
                {
                    "label": "Summary",
                    "name": "summary",
                    "type": "textarea",
                    "hint": "Provide solution description",
                    "value": self.outage.solution.summary or "",
                    "optional": True,
                },
                {
                    "label": "Sales affected",
                    "type": "select",
                    "options": SALES_AFFECTED_CHOICE_OPT_SOLUTION,
                    "name": "sales_affected_choice",
                    "value": sales_affected,
                    "hint": "If sales have been affected choose Postmortem report in Suggested outcome.",
                },
                {
                    "label": "Lost bookings",
                    "type": "text",
                    "name": "lost_bookings",
                    "subtype": "number",
                    "optional": True,
                    "value": self.outage.lost_bookings,
                    "hint": "Specify how many bookings have been lost if any (e.g. 100).",
                },
                {
                    "label": "Impact on turnover",
                    "type": "text",
                    "name": "impact_on_turnover",
                    "subtype": "number",
                    "optional": True,
                    "value": self.outage.impact_on_turnover,
                    "hint": "Specify impact on turnover in EUR, if any (e.g. 1000).",
                },
                {
                    "type": "text",
                    "label": "Resolved at",
                    "name": "real_downtime",
                    "value": timezone.localtime(timezone=self.user_tz).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "hint": "Local time",
                },
                {
                    "label": "Suggested outcome",
                    "type": "select",
                    "name": "outcome",
                    "options": OUTCOME_OPT,
                    "optional": True,
                    "value": Solution.NONE,
                },
            ],
        }

    def addsystem(self):
        return {
            "callback_id": f"{self.outage.id}_addsystem",
            "title": f"Add primary affected system",
            "submit_label": "Add",
            "notify_on_cancel": True,
            "elements": [
                {
                    "label": "Primary affected system",
                    "type": "select",
                    "name": "affected_system",
                    "options": get_system_option(),
                    "hint": "Select primary affected system.",
                }
            ],
        }

    def removesystem(self):
        return {
            "callback_id": f"{self.outage.id}_removesystem",
            "title": f"Add primary affected system",
            "submit_label": "Remove",
            "notify_on_cancel": True,
            "elements": [
                {
                    "label": "Primary affected system",
                    "type": "select",
                    "name": "affected_system",
                    "options": get_system_option(),
                    "hint": "Select primary affected system.",
                }
            ],
        }

    def edit_solution(self):
        solution = self.outage.solution
        return {
            "callback_id": f"{self.outage.id}_editsolved",
            "title": f"{self.outage.summary[:20]}...",
            "submit_label": "Update",
            "notify_on_cancel": True,
            "elements": [
                {
                    "label": "Summary",
                    "name": "summary",
                    "type": "textarea",
                    "hint": "Provide solution description",
                    "value": solution.summary,
                    "optional": True,
                },
                {
                    "label": "Sales affected",
                    "type": "select",
                    "options": SALES_AFFECTED_CHOICE_OPT_SOLUTION,
                    "name": "sales_affected_choice",
                    "value": self.outage.sales_affected_choice,
                    "hint": "If sales have been affected choose Postmortem report in Suggested outcome.",
                },
                {
                    "label": "Lost bookings",
                    "type": "text",
                    "name": "lost_bookings",
                    "subtype": "number",
                    "optional": True,
                    "value": self.outage.lost_bookings,
                    "hint": "Specify how many bookings have been lost if any (e.g. 100).",
                },
                {
                    "label": "Impact on turnover",
                    "type": "text",
                    "name": "impact_on_turnover",
                    "subtype": "number",
                    "optional": True,
                    "value": self.outage.impact_on_turnover,
                    "hint": "Specify impact on turnover in EUR, if any (e.g. 1000).",
                },
                {
                    "label": "Suggested outcome",
                    "type": "select",
                    "name": "outcome",
                    "options": OUTCOME_OPT,
                    "value": solution.suggested_outcome,
                },
                {
                    "label": "Link to report",
                    "name": "report_url",
                    "type": "text",
                    "subtype": "url",
                    "value": solution.report_url,
                    "hint": "Full URL to postmortem",
                    "optional": True,
                },
            ],
        }

    def edit_duration(self):
        solution = self.outage.solution
        resolved_at = utc_to_user_time(arrow.get(solution.resolved_at), self.user_tz)
        started_at = utc_to_user_time(
            arrow.get(solution.outage.started_at), self.user_tz
        )
        return {
            "callback_id": f"{self.outage.id}_editduration",
            "title": f"{self.outage.summary[:20]}...",
            "submit_label": "Update",
            "notify_on_cancel": True,
            "elements": [
                {
                    "type": "text",
                    "label": "Started at",
                    "name": "started_at",
                    "value": started_at.strftime("%Y-%m-%d %H:%M"),
                },
                {
                    "type": "text",
                    "label": "Resolved at",
                    "name": "resolved_at",
                    "value": resolved_at.strftime("%Y-%m-%d %H:%M"),
                },
            ],
        }

    def create_channel(self):
        self.outage.announcement.create_dedicated_channel = True
        self.outage.announcement.save(update_fields=["create_dedicated_channel"])

    def assign_channel(self):
        return {
            "callback_id": f"{self.outage.id}_assignchannel",
            "title": f"Assign slack channel",
            "submit_label": "Update",
            "notify_on_cancel": True,
            "elements": [
                {
                    "label": "Slack channel",
                    "name": "channel",
                    "type": "select",
                    "data_source": "channels",
                }
            ],
        }

    def attach_report(self):
        return {
            "callback_id": f"{self.outage.id}_attachreport",
            "title": f"Attach outage report",
            "submit_label": "Update",
            "notify_on_cancel": True,
            "elements": [
                {
                    "label": "Link to report",
                    "name": "report_url",
                    "type": "text",
                    "subtype": "url",
                    "hint": "Full URL to postmortem",
                    "optional": True,
                }
            ],
        }

    def set_eta(self):
        """Use for ETA update prompt."""
        if not self.outage.prompt_active:
            data = slack_bot_client.api_call(
                "chat.delete",
                channel=self.payload["channel"]["id"],
                ts=self.payload["message_ts"],
            )
            if not data["ok"]:
                logger.error(f"ETA prompt update error: {data}")
            return
        new_eta = int(self.action["value"])
        self.outage.set_eta(new_eta)
        self.outage.prompt_active = False
        self.outage.save(modified_by=self.actor)

        data = slack_bot_client.api_call(
            "chat.delete",
            channel=self.payload["channel"]["id"],
            ts=self.payload["message_ts"],
        )
        if not data["ok"]:
            logger.error(f"ETA prompt update error: {data}")

    def reopen_outage(self):
        self.outage.resolved = False
        self.outage.save(modified_by=self.actor)


def handle_interactive_message(request, payload):
    message_handler = InteractiveMesssageHandler(request, payload)
    message_handler.handle()


class DialogSubmissionHandler:
    def __init__(self, request, payload):
        self.request = request
        self.callback_id = payload.get("callback_id")
        m = callback_pattern.match(self.callback_id)
        if m is not None:
            self.obj = m.group(1)
            self.action = m.group(2)

        self.dialog_data = payload.get("submission")
        self.actor = provision_slack_user(payload["user"]["id"])
        self.errors = []

    def handle(self):
        handler = getattr(self, self.action, None)
        if handler:
            data = handler()
            if self.errors:
                return Response(data={"errors": self.errors}, status=status.HTTP_200_OK)
            if data:
                return data

    def edit(self):
        eta = self.dialog_data.get("eta")
        lost_bookings = self.dialog_data.get("lost_bookings")
        impact_on_turnover = self.dialog_data.get("impact_on_turnover")
        if eta:
            try:
                int(eta)
            except ValueError:
                self.errors.append(
                    {
                        "name": "eta",
                        "error": "Invalid format. Specify ETA in minutes (for example: 30).",
                    }
                )
        if lost_bookings:
            try:
                int(lost_bookings)
            except ValueError:
                self.errors.append(
                    {
                        "name": "lost_bookings",
                        "error": "Invalid format. Needs to be specified as number (e.g. 1000).",
                    }
                )
        if impact_on_turnover:
            try:
                int(impact_on_turnover)
            except ValueError:
                self.errors.append(
                    {
                        "name": "impact_on_turnover",
                        "error": "Invalid format. Needs to be specified as number (e.g. 1000).",
                    }
                )
        if self.errors:
            return

        outage = Outage.objects.get(id=self.obj)
        outage.set_eta(eta)
        change_desc = self.dialog_data.get("more_info", 0)
        outage.sales_affected_choice = self.dialog_data.get("sales_affected_choice")
        outage.lost_bookings = lost_bookings
        outage.impact_on_turnover = impact_on_turnover
        outage.save(change_desc=change_desc, modified_by=self.actor)

    def editassignees(self):
        outage = Outage.objects.get(id=self.obj)
        outage.make_solution_assignee(self.dialog_data.get("solution_assignee"))
        outage.make_communication_assignee(
            self.dialog_data.get("communication_assignee")
        )
        outage.save(modified_by=self.actor)

    def new(self):
        eta = self.dialog_data.get("eta")
        lost_bookings = self.dialog_data.get("lost_bookings")
        impact_on_turnover = self.dialog_data.get("impact_on_turnover")
        if eta:
            try:
                int(eta)
            except ValueError:
                self.errors.append(
                    {
                        "name": "eta",
                        "error": "Invalid format. Specify ETA in minutes (for example: 30).",
                    }
                )
        if lost_bookings:
            try:
                int(lost_bookings)
            except ValueError:
                self.errors.append(
                    {
                        "name": "lost_bookings",
                        "error": "Invalid format. Needs to be specified as number (e.g. 1000).",
                    }
                )
        if impact_on_turnover:
            try:
                int(impact_on_turnover)
            except ValueError:
                self.errors.append(
                    {
                        "name": "impact_on_turnover",
                        "error": "Invalid format. Needs to be specified as number (e.g. 1000).",
                    }
                )
        if self.errors:
            return

        outage = Outage(
            summary=self.dialog_data.get("summary"),
            created_by=self.request.user,
            sales_affected_choice=self.dialog_data.get("sales_affected_choice"),
            lost_bookings=lost_bookings,
            impact_on_turnover=impact_on_turnover,
        )
        outage.set_eta(eta)
        affected_system = self.dialog_data.get("affected_system")
        outage.set_system_affected(affected_system)
        outage.save()

    def resolve(self):
        outage = Outage.objects.get(id=self.obj)
        user_tz = self.request.user.profile.timezone
        lost_bookings = self.dialog_data.get("lost_bookings")
        impact_on_turnover = self.dialog_data.get("impact_on_turnover")
        try:
            # TODO: fix midnight
            resolved_at = arrow.get(
                self.dialog_data.get("real_downtime"), "YYYY-MM-DD HH:mm"
            )
            resolved_at = resolved_at_to_utc(resolved_at, user_tz)
        except (ValueError, arrow.parser.ParserError):
            self.errors.append({"name": "real_downtime", "error": "Invalid format."})
        if lost_bookings:
            try:
                int(lost_bookings)
            except ValueError:
                self.errors.append(
                    {
                        "name": "lost_bookings",
                        "error": "Invalid format. Needs to be specified as number (e.g. 1000).",
                    }
                )
        if impact_on_turnover:
            try:
                int(impact_on_turnover)
            except ValueError:
                self.errors.append(
                    {
                        "name": "impact_on_turnover",
                        "error": "Invalid format. Needs to be specified as number (e.g. 1000).",
                    }
                )
        if self.errors:
            return
        solution = outage.solution
        solution.resolved_at = resolved_at
        solution.summary = self.dialog_data.get("summary")
        solution.suggested_outcome = self.dialog_data.get("outcome")
        outage.sales_affected_choice = self.dialog_data.get("sales_affected_choice")
        outage.lost_bookings = lost_bookings
        outage.impact_on_turnover = impact_on_turnover
        outage.prompt_for_eta_update = False

        if not outage.resolved:
            outage.resolved = True
        solution.outage.save(modified_by=self.actor)
        solution.save(modified_by=self.actor)

    def editsolved(self):  # Ignore RadonBear
        outage = Outage.objects.get(id=self.obj)
        solution = outage.solution
        lost_bookings = self.dialog_data.get("lost_bookings")
        impact_on_turnover = self.dialog_data.get("impact_on_turnover")
        if lost_bookings:
            try:
                int(lost_bookings)
            except ValueError:
                self.errors.append(
                    {
                        "name": "lost_bookings",
                        "error": "Invalid format. Needs to be specified as number (e.g. 1000).",
                    }
                )
        if impact_on_turnover:
            try:
                int(impact_on_turnover)
            except ValueError:
                self.errors.append(
                    {
                        "name": "impact_on_turnover",
                        "error": "Invalid format. Needs to be specified as number (e.g. 1000).",
                    }
                )
        if self.errors:
            return

        if self.dialog_data.get("summary"):
            solution.summary = self.dialog_data.get("summary")
        if self.dialog_data.get("outcome"):
            solution.suggested_outcome = self.dialog_data.get("outcome")
        if self.dialog_data.get("report_url"):
            solution.report_url = self.dialog_data.get("report_url")
            title = get_postmortem_title(solution.report_url)
            if title:
                solution.report_title = title
            elif not title and solution.report_title:
                solution.report_title = ""
        outage.sales_affected_choice = self.dialog_data.get("sales_affected_choice")
        outage.lost_bookings = lost_bookings
        outage.impact_on_turnover = impact_on_turnover
        outage.save(modified_by=self.actor)
        solution.save(modified_by=self.actor)

    def editduration(self):
        outage = Outage.objects.get(id=self.obj)
        solution = outage.solution
        user_tz = self.request.user.profile.timezone
        try:
            # TODO: fix midnight
            resolved_at = arrow.get(
                self.dialog_data.get("resolved_at"), "YYYY-MM-DD HH:mm"
            )
            resolved_at = resolved_at_to_utc(resolved_at, user_tz)
        except (ValueError, arrow.parser.ParserError):
            self.errors.append({"name": "resolved_at", "error": "Invalid format."})
        try:
            started_at = arrow.get(
                self.dialog_data.get("started_at"), "YYYY-MM-DD HH:mm"
            )
            started_at = resolved_at_to_utc(started_at, user_tz)
        except (ValueError, arrow.parser.ParserError):
            self.errors.append({"name": "started_at", "error": "Invalid format."})
        if started_at > resolved_at:
            self.errors += [
                {
                    "name": "started_at",
                    "error": "Outage can't be resolved before it started. Please fix the Start and Resolve times.",
                },
                {
                    "name": "resolved_at",
                    "error": "Outage can't be resolved before it started. Please fix the Start and Resolve times.",
                },
            ]
        if self.errors:
            return

        solution.resolved_at = resolved_at
        outage.started_at = started_at

        outage.save(modified_by=self.actor)
        solution.save(modified_by=self.actor)

    def assignchannel(self):
        channel_id = self.dialog_data.get("channel")
        if channel_id:
            create_channel_task.delay(self.obj, channel_id=channel_id)

    def attachreport(self):
        outage = Outage.objects.get(id=self.obj)
        solution = outage.solution
        if not solution.report_url:
            report_url = self.dialog_data.get("report_url")
            if report_url and not report_url.startswith("http"):
                report_url = f"https://{report_url}"
            solution.report_url = report_url

            title = get_postmortem_title(report_url)
            if title:
                solution.report_title = title
            elif not title and solution.report_title:
                solution.report_title = ""

            outage.save(
                modified_by=self.actor
            )  # NOTE: hotfix for broken comment system
            solution.save(modified_by=self.actor)


def handle_dialog_submission(request, payload):  # Ignore RadonBear
    submission_handler = DialogSubmissionHandler(request, payload)
    return submission_handler.handle()
