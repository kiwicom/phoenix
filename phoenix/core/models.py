import logging
import re

import arrow
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models
from django.utils import timezone

logger = logging.getLogger(__name__)


USER_MODEL = settings.AUTH_USER_MODEL

ETA_PARSE_RE = re.compile(r"(?P<symbol>[<>]?)(?P<value>\d+)(?P<granularity>\w{1})")


class Profile(models.Model):
    user = models.OneToOneField(USER_MODEL, on_delete=models.CASCADE)
    timezone = models.TextField(null=False, default="Etc/UTC")
    image_48_url = models.TextField(null=True, blank=True)
    slack_username = models.CharField(null=True, blank=True, max_length=150)

    def __str__(self):
        return f"Profile {self.id} for User {self.user.id}"

    @property
    def slack_link(self):
        return f"https://skypicker.slack.com/team/{self.user.last_name}"


class System(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        ordering = ["name"]


class RootCause(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        ordering = ["name"]


class AbstractOutage(models.Model):
    YES = "Y"
    NO = "N"
    UNKNOWN = "UN"
    SALES_AFFECTED_CHOICES = ((YES, "yes"), (NO, "no"), (UNKNOWN, "unknown"))

    ETA_CHOICES = (
        ("<30m", "<30m"),
        ("<2h", "<2h"),
        ("<8h", "<8h"),
        ("<24h", "<24h"),
        (
            ">24h",
            ">24h",
        ),  # symbol ">" will be evaluated as unknown ETA in eta_in_minutes
    )
    LOST_BOOKINGS_CHOICES = (
        ("0%", "0%"),
        ("<30%", "<30%"),
        ("<60%", "<60%"),
        ("<100%", "<100%"),
        ("100%", "100%"),
    )

    summary = models.TextField(null=False, blank=False, max_length=3000)
    systems_affected = models.ForeignKey(
        System, null=True, related_name="systems_%(class)s", on_delete=models.CASCADE
    )
    root_cause = models.ForeignKey(RootCause, null=True, on_delete=models.CASCADE)
    communication_assignee = models.ForeignKey(
        USER_MODEL, related_name="comunicate_outages", on_delete=models.CASCADE
    )
    solution_assignee = models.ForeignKey(
        USER_MODEL, related_name="solves_outages", on_delete=models.CASCADE
    )
    created = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        USER_MODEL, related_name="outage_created", on_delete=models.CASCADE
    )
    started_at = models.DateTimeField(default=timezone.now)
    announce_on_slack = models.BooleanField(default=True)

    sales_affected_choice = models.CharField(
        choices=SALES_AFFECTED_CHOICES, max_length=2, default=UNKNOWN
    )
    # Keeping field sales_affected for compatibility reasons. This field will also be filled with data from fields
    # lost_bookings and impact_on_turnover.
    sales_affected = models.TextField(max_length=3000, null=True, blank=True)
    lost_bookings = models.TextField(max_length=3000, null=True, blank=True)
    lost_bookings_choice = models.CharField(
        choices=LOST_BOOKINGS_CHOICES, max_length=5, null=False, blank=False
    )
    impact_on_turnover = models.IntegerField(null=True, blank=True)

    eta = models.CharField(choices=ETA_CHOICES, max_length=6, null=False, blank=False)
    eta_last_modified = models.DateTimeField(null=True)

    # Needed for re-open outage functionality
    resolved = models.BooleanField(default=False)

    class Meta:
        abstract = True

    @property
    def sales_has_been_affected(self):
        return self.sales_affected_choice == self.YES

    @property
    def sales_affected_choice_human(self):
        return [
            s[1]
            for s in self.SALES_AFFECTED_CHOICES
            if s[0] == self.sales_affected_choice
        ][0]

    @property
    def systems_affected_human(self):
        return self.systems_affected.name or "N/A"

    @property
    def created_timestamp(self):
        return int(self.created.timestamp())


class Outage(AbstractOutage):
    # If outage isn't resolved ping communication assignee every X minutes.
    # This field holds the time of the last ping.
    communication_assignee_last_notified = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Outage {self.id}"

    def communication_assignee_notified(self):
        self.communication_assignee_last_notified = arrow.now().datetime

    @property
    def is_resolved(self):
        try:
            if self.resolved and self.solution is not None:
                return self.solution
            return False
        except ObjectDoesNotExist:
            return False

    @property
    def is_reopened(self):
        return self.solution is not None and not self.resolved

    def set_eta(self, eta):
        """Properly sets eta. Never change eta manually.

        This method will set eta and eta_last_modifie values.
        Both are needed for proper representation.
        """
        self.eta = eta
        self.eta_last_modified = timezone.now()

    @property
    def eta_in_minutes(self):
        granularity_table = {"m": 1, "h": 60}
        m = ETA_PARSE_RE.match(self.eta)
        value = m.groupdict()["value"]
        granularity = m.groupdict()["granularity"]
        symbol = m.groupdict()["symbol"]
        if symbol == ">":
            # symbol ">" is only used for last value that is represented as unknown ETA
            return None
        x = granularity_table[granularity]
        return int(value) * x

    @property
    def eta_deadline(self):
        eta_in_minutes = self.eta_in_minutes
        if not eta_in_minutes:
            return ""
        eta_last_modified = arrow.get(self.eta_last_modified)
        return eta_last_modified.shift(minutes=eta_in_minutes)

    @property
    def eta_remaining(self):
        """Calculate remaining ETA from now in minutes."""
        eta_deadline = self.eta_deadline
        if not eta_deadline:
            return ""
        delta = eta_deadline - arrow.utcnow()
        minutes = delta.total_seconds() // 60
        minutes = int(minutes)
        if minutes <= 0:
            return 0
        return minutes

    def _make_assignee(self, user_last_name, column="solution_assignee"):
        if not user_last_name:
            return
        try:
            user = get_user_model().objects.get(last_name=user_last_name)
        except get_user_model().DoesNotExist:
            logger.error(f"Can't assign user: {user_last_name}")
            return
        setattr(self, column, user)

    def make_solution_assignee(self, user_last_name):
        self._make_assignee(user_last_name)

    def make_communication_assignee(self, user_last_name):
        self._make_assignee(user_last_name, column="communication_assignee")

    def set_system_affected(self, system_id):
        try:
            system = System.objects.get(id=system_id)
        except System.DoesNotExist:
            return False
        self.systems_affected = system

    def set_root_cause(self, root_cause_id):
        try:
            root_cause = RootCause.objects.get(id=root_cause_id)
        except RootCause.DoesNotExist:
            return False
        self.root_cause = root_cause

    def add_notification(self, text, by_user):
        self.notifications.create(text=text, created_by=by_user)

    def get_involved_users(self):
        """Return list of involved users."""
        return [self.created_by, self.solution_assignee, self.communication_assignee]

    def get_involved_user_ids(self):
        """Return IDs of creater and assignees."""
        involved_users = [a.id for a in self.get_involved_users()]
        return involved_users

    def can_edit_outage(self, user_id):
        """Check if user is linked to outage."""
        return user_id in self.get_involved_user_ids()

    def lost_bookings_human(self):
        msg = f"{self.lost_bookings_choice} lost bookings"
        if self.lost_bookings:
            msg += f", {self.lost_bookings}"
        msg += "."
        return msg

    def impact_on_turnover_human(self):
        return f"{self.impact_on_turnover or 'N/A'} EUR impact on turnover."

    def fill_sales_affected(self):
        self.sales_affected = (
            f"{self.lost_bookings_human()} {self.impact_on_turnover_human()}"
        )

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        change_desc = kwargs.pop("change_desc", None)
        modified_by = kwargs.pop("modified_by", None)
        self.summary = self.summary.strip()

        self.fill_sales_affected()

        if self.pk is None:
            try:
                self.communication_assignee
            except ObjectDoesNotExist:
                self.communication_assignee = self.created_by
            try:
                self.solution_assignee
            except ObjectDoesNotExist:
                self.solution_assignee = self.created_by

        super(Outage, self).save(*args, **kwargs)

        history = OutageHistory.objects.create(
            summary=self.summary,
            sales_affected_choice=self.sales_affected_choice,
            sales_affected=self.sales_affected,
            lost_bookings=self.lost_bookings,
            lost_bookings_choice=self.lost_bookings_choice,
            impact_on_turnover=self.impact_on_turnover,
            communication_assignee=self.communication_assignee,
            solution_assignee=self.solution_assignee,
            created=self.created,
            created_by=self.created_by,
            eta=self.eta,
            eta_last_modified=self.eta_last_modified,
            outage=self,
            change_desc=change_desc,
            modified_by=modified_by,
            started_at=self.started_at,
            systems_affected=self.systems_affected,
            resolved=self.resolved,
            root_cause=self.root_cause,
        )
        history.save()

    class Meta:
        ordering = ["-pk"]


class OutageHistory(AbstractOutage):
    modified_by = models.ForeignKey(
        USER_MODEL, null=True, blank=True, on_delete=models.CASCADE
    )
    outage = models.ForeignKey(
        Outage, related_name="history_outage", on_delete=models.CASCADE
    )
    change_desc = models.TextField(null=True, blank=True, max_length=3000)
    timestamp = models.DateTimeField(auto_now_add=True)
    # name colisions
    created_by = models.ForeignKey(
        USER_MODEL, related_name="history_outage_created", on_delete=models.CASCADE
    )
    resolved_by = models.ForeignKey(
        USER_MODEL,
        related_name="history_outage_resolved",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    communication_assignee = models.ForeignKey(
        USER_MODEL, related_name="history_comunicate_outages", on_delete=models.CASCADE
    )
    solution_assignee = models.ForeignKey(
        USER_MODEL, related_name="history_solves_outages", on_delete=models.CASCADE
    )

    def __str__(self):
        return f"History Outage {self.id} for Outage {self.outage.id}"

    class Meta:
        ordering = ["-pk"]


class PostmortemNotifications(models.Model):
    slack_notified = models.BooleanField(default=False)
    email_notified = models.BooleanField(default=False)
    label_notified = models.BooleanField(default=False)


class AbstractSolution(models.Model):
    class Meta:
        abstract = True

    POSTMORTEM = "PM"
    NONE = "NO"
    OUTCOME_CHOICES = ((POSTMORTEM, "Postmortem report"), (NONE, "None"))

    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        USER_MODEL,
        related_name="solution_created",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    summary = models.TextField(max_length=3000, null=True, blank=True)
    resolved_at = models.DateTimeField(default=timezone.now)
    solving_time = models.IntegerField(default=0)
    suggested_outcome = models.CharField(
        choices=OUTCOME_CHOICES, default=NONE, max_length=2
    )
    report_url = models.TextField(null=True, blank=True)
    report_title = models.TextField(null=True, blank=True)

    @property
    def suggested_outcome_human(self):
        return [c for k, c in self.OUTCOME_CHOICES if k == self.suggested_outcome][0]


class SolutionManager(models.Manager):
    def outcome_is_postmortem(self):
        return self.filter(suggested_outcome=AbstractSolution.POSTMORTEM)


class Solution(AbstractSolution):
    objects = SolutionManager()

    outage = models.OneToOneField(Outage, on_delete=models.CASCADE)
    postmortem_notifications = models.OneToOneField(
        PostmortemNotifications, on_delete=models.CASCADE, null=True, blank=True
    )

    @property
    def postmortem_required(self):
        return self.suggested_outcome == self.POSTMORTEM

    def get_postmortem_notifications(self):
        if self.postmortem_required:
            try:
                return self.postmortem_notifications
            except PostmortemNotifications.DoesNotExist:
                return None
        return None

    def downtime(self):
        start = arrow.get(self.outage.started_at)
        end = arrow.get(self.resolved_at)
        if start > end:
            # TODO: resolved_at is always set to HH:mm:00. When outage is resolved
            # at the same minute, the self.resolved_at will be less.
            return 0
        diff = end - start
        return diff

    @property
    def real_downtime(self):
        downtime = self.downtime()
        if not downtime:
            return 0
        minutes = downtime.seconds // 60
        return minutes

    def duration(self):
        downtime = self.downtime()
        if not downtime:
            return 0, 0, 0, 0
        days = downtime.days
        seconds = downtime.seconds
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return days, hours, minutes, seconds

    @property
    def resolved_at_timestamp(self):
        return arrow.get(self.resolved_at).timestamp

    @property
    def missing_postmortem(self):
        if self.postmortem_required:
            return not self.report_url
        return False

    @property
    def full_report_url(self):
        if self.report_url and not self.report_url.startswith("http"):
            return f"https://{self.report_url}"
        return self.report_url

    def __str__(self):
        return f"Solution {self.pk}"

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        modified_by = kwargs.pop("modified_by", None)
        if self.summary:
            self.summary = self.summary.strip()
        super().save(*args, **kwargs)

        SolutionHistory.objects.create(
            solution=self,
            modified_by=modified_by,
            created_by=self.created_by,
            summary=self.summary,
            resolved_at=self.resolved_at,
            solving_time=self.solving_time,
            suggested_outcome=self.suggested_outcome,
            report_url=self.report_url,
        )

    class Meta:
        ordering = ["-pk"]


class SolutionHistory(AbstractSolution):
    modified_by = models.ForeignKey(
        USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    # name clashes
    created_by = models.ForeignKey(
        USER_MODEL,
        related_name="history_solution_created",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    solution = models.ForeignKey(
        Solution, related_name="solution_history", on_delete=models.CASCADE
    )

    class Meta:
        ordering = ["-pk"]


class Notification(models.Model):
    created = models.DateTimeField(default=timezone.now)
    text = models.TextField(null=False, blank=False)
    outage = models.ForeignKey(
        Outage, related_name="notifications", on_delete=models.CASCADE
    )
    created_by = models.ForeignKey(
        USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        return f"Notification {self.id} for Outage {self.outage.id}"

    class Meta:
        ordering = ["-pk"]


class AbstractMonitor(models.Model):
    LOW = "LO"
    MEDIUM = "ME"
    HIGH = "HI"
    UNDEFINED = "UN"

    SEVERITY_CHOICES = (
        (UNDEFINED, "undefined"),
        (LOW, "low"),
        (MEDIUM, "medium"),
        (HIGH, "high"),
    )

    DATADOG = "DD"
    PINGDOM = "PD"

    MONITORING_SYSTEM_CHOICES = (
        (UNDEFINED, "Undefined"),
        (DATADOG, "Datadog"),
        (PINGDOM, "Pingdom"),
    )

    monitoring_system = models.CharField(
        max_length=2, choices=MONITORING_SYSTEM_CHOICES, default=UNDEFINED
    )
    external_id = models.CharField(blank=False, null=False, max_length=100)
    created = models.DateTimeField(default=timezone.now)
    link = models.CharField(max_length=200)
    severity = models.CharField(
        choices=SEVERITY_CHOICES, default=UNDEFINED, max_length=2
    )
    description = models.TextField(blank=True, null=True, max_length=3000)
    created_by = models.CharField(blank=True, null=True, max_length=200)
    name = models.CharField(blank=True, null=True, max_length=300)
    slack_channel_id = models.CharField(blank=True, null=True, max_length=10)
    slack_channel_name = models.CharField(blank=True, null=True, max_length=22)

    class Meta:
        abstract = True

    def occurrence_count(self):
        return Alert.objects.filter(monitor=self).count()

    def add_occurrence(self, alert_type, alert_ts):
        try:
            alert = Alert(monitor=self, alert_type=alert_type, ts=alert_ts)
            alert.save()
        except IntegrityError:
            logger.info(f"{alert} already exists!")


class Monitor(AbstractMonitor):
    class Meta:
        unique_together = ("monitoring_system", "external_id")

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        modified_by = kwargs.pop("modified_by", None)

        super().save(*args, **kwargs)

        MonitorHistory.objects.create(
            modified_by=modified_by,
            monitor=self,
            created=self.created,
            external_id=self.external_id,
            link=self.link,
            severity=self.severity,
            description=self.description,
            created_by=self.created_by,
            monitoring_system=self.monitoring_system,
            slack_channel_id=self.slack_channel_id,
            slack_channel_name=self.slack_channel_name,
        )

    def last_modification(self):
        last_modification = self.history.last()
        return last_modification.modified_by, last_modification.timestamp


class MonitorHistory(AbstractMonitor):
    modified_by = models.ForeignKey(
        USER_MODEL, blank=True, null=True, on_delete=models.CASCADE
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    monitor = models.ForeignKey(
        Monitor, blank=True, null=True, related_name="history", on_delete=models.CASCADE
    )
    external_id = models.CharField(blank=False, null=False, max_length=100)


class Alert(models.Model):
    UNDEFINED = "UN"
    WARNING = "WA"
    CRITICAL = "CR"

    TYPE_CHOICES = (
        (UNDEFINED, "undefined"),
        (WARNING, "warning"),
        (CRITICAL, "critical"),
    )

    created = models.DateTimeField(auto_now_add=True)
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE)
    ts = models.DateTimeField(null=True, default=None)
    alert_type = models.CharField(
        blank=False, null=False, choices=TYPE_CHOICES, default=UNDEFINED, max_length=2
    )

    class Meta:
        unique_together = ("monitor", "ts")

    def __str__(self):
        return f"Alert monitor={self.monitor.external_id} ts={self.ts}"
