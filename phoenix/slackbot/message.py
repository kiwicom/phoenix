from django.urls import reverse

from . import utils
from ..core.models import Solution

SLACK_FIELDS = {
    "sales": {"title": "Impact on sales"},
    "eta": {"title": "ETA", "short": True},
    "assigneess": {"title": "Assignees", "short": True},
    "duration": {"title": "Duration", "short": True},
    "resolution": {"title": "Resolution"},
}

SLACK_ACTIONS = {
    "edit": {"name": "edit", "text": "Edit", "type": "button", "value": "edit"},
    "edit_assignees": {
        "name": "edit_assignees",
        "text": "Reassign",
        "type": "button",
        "value": "edit_assignees",
    },
    "resolve": {
        "name": "resolve",
        "text": "Resolve",
        "type": "button",
        "style": "primary",
        "value": "resolve",
    },
    "edit_solution": {
        "name": "edit_solution",
        "text": "Edit",
        "type": "button",
        "value": "edit_solution",
    },
    "attach_report": {
        "name": "attach_report",
        "text": "Link Post-mortem",
        "type": "button",
        "value": "attach_report",
    },
    "create_channel": {
        "name": "create_channel",
        "text": "Create channel",
        "type": "button",
        "value": "create_channel",
    },
    "assign_channel": {
        "name": "assign_channel",
        "text": "Set channel",
        "type": "button",
        "value": "assign_channel",
    },
    "edit_duration": {
        "name": "edit_duration",
        "text": "Edit Duration",
        "type": "button",
        "value": "edit_duration",
    },
}


def slack_field(field_name, value=None):
    field = SLACK_FIELDS[field_name]
    field["value"] = value
    return field


class BaseMessage:
    def __init__(self, outage, announcement):
        self.outage = outage
        self.announcement = announcement
        self.title = f"{self.outage.systems_affected_human} incident"

    def generate_message(self):
        attachment = self.generate_base()
        attachment = self.generate_specific(attachment)
        return [attachment]

    def generate_base(self):
        outage_rel_link = reverse("outage_detail", kwargs={"pk": self.outage.pk})
        outage_abs_link = utils.get_absolute_url(outage_rel_link)
        attachment = {
            "callback_id": self.outage.id,
            "fallback": f"{self.title} - {self.outage.summary}",
            "color": self.color,
            "title": self.title,
            "title_link": outage_abs_link,
            "attachment_type": "default",
            "text": self.outage.summary,
            "fields": [],
        }
        return attachment

    def generate_specific(self, attachment):
        raise NotImplementedError

    def get_formatted_sales(self):
        """Return sales affected formatted for slack."""
        msg = f"{self.outage.sales_affected_choice_human.capitalize()}."
        if self.outage.sales_affected:
            msg += f" {self.outage.sales_affected}"
        return msg

    def get_formatted_assigneess(self):
        """Return assignees formated for slack."""
        solution_assignee = utils.format_user_for_slack(self.outage.solution_assignee)
        communication_assignee = utils.format_user_for_slack(
            self.outage.communication_assignee
        )
        return f"{solution_assignee} for resolution\n{communication_assignee} for communication"


class SolutionMessage(BaseMessage):
    def __init__(self, outage, announcement):
        super().__init__(outage, announcement)
        self.solution = outage.is_resolved
        self.title = (
            self.solution.report_title
            if self.solution.report_title
            else "Resolved " + self.title
        )
        self.color = "good"

    def get_formatted_resolution(self):
        resolution = f"{self.solution.summary}"

        outcome = self.solution.suggested_outcome
        if outcome == Solution.POSTMORTEM:
            if self.solution.report_url:
                report_url = self.solution.full_report_url
                resolution += f"\n\nSee <{report_url}|post-mortem report>."
            else:
                resolution += f"\n\nPost-mortem report will be created."
        return resolution

    def get_formatted_duration(self):
        days, hours, minutes, _ = self.solution.duration()
        duration = f"{minutes}m"
        if hours:
            duration = f"{hours}h " + duration
        if days:
            duration = f"{days}d " + duration
        return duration

    def add_fields(self, attachment):
        attachment["fields"] = [
            slack_field("sales", value=self.get_formatted_sales()),
            slack_field("resolution", value=self.get_formatted_resolution()),
            slack_field("assigneess", value=self.get_formatted_assigneess()),
            slack_field("duration", value=self.get_formatted_duration()),
        ]
        return attachment

    def add_actions(self, attachment):
        attachment["actions"] = [
            SLACK_ACTIONS["edit_solution"],
            SLACK_ACTIONS["edit_duration"],
        ]
        if not self.solution.report_url:
            attachment["actions"] += [SLACK_ACTIONS["attach_report"]]
        return attachment

    def add_footer(self, attachment):
        resolver = utils.format_user_for_slack(self.solution.created_by)
        footer_msg = f"Outage was resolved by {resolver}"
        attachment["footer"] = footer_msg
        attachment["ts"] = self.solution.resolved_at.timestamp()
        attachment["footer_icon"] = (
            "https://slack-imgs.com/?c=1&o1=wi32.he32.si&url=https%3A%2F%2Fs3-us-west-2"
            ".amazonaws.com%2Fpd-slack%2Ficons%2Fresolved.png"
        )
        return attachment

    def generate_specific(self, attachment):
        attachment = self.add_fields(attachment)
        attachment = self.add_actions(attachment)
        attachment = self.add_footer(attachment)
        return attachment


class OutageMessage(BaseMessage):
    def __init__(self, outage, announcement):
        super().__init__(outage, announcement)
        self.color = "danger"

    def add_fields(self, attachment):
        attachment["fields"] = [
            slack_field("sales", value=self.get_formatted_sales()),
            slack_field("assigneess", value=self.get_formatted_assigneess()),
            slack_field(
                "eta",
                value="Unknown"
                if self.outage.eta_is_unknown
                else utils.format_datetime(self.outage.eta_deadline),
            ),
        ]
        return attachment

    def add_actions(self, attachment):
        attachment["actions"] = [
            SLACK_ACTIONS["resolve"],
            SLACK_ACTIONS["edit"],
            SLACK_ACTIONS["edit_assignees"],
        ]
        if not self.announcement.dedicated_channel_id:
            attachment["actions"] += [
                SLACK_ACTIONS["create_channel"],
                SLACK_ACTIONS["assign_channel"],
            ]
        return attachment

    def generate_specific(self, attachment):
        attachment = self.add_fields(attachment)
        attachment = self.add_actions(attachment)
        return attachment


def generate_slack_message(outage, announcement):
    if outage.is_resolved:
        return SolutionMessage(outage, announcement).generate_message()
    return OutageMessage(outage, announcement).generate_message()
