import logging

import arrow
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models
from django.utils import timezone

logger = logging.getLogger(__name__)


USER_MODEL = settings.AUTH_USER_MODEL


class Profile(models.Model):
    user = models.OneToOneField(USER_MODEL, on_delete=models.CASCADE)
    timezone = models.TextField(null=False, default='Etc/UTC')
    image_48_url = models.TextField(null=True, blank=True)
    slack_username = models.CharField(null=True, blank=True, max_length=150)

    def __str__(self):
        return f'Profile {self.id} for User {self.user.id}'

    @property
    def slack_link(self):
        return f'https://skypicker.slack.com/team/{self.user.last_name}'


class System(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        ordering = ['name']


class AbstractOutage(models.Model):
    YES = 'Y'
    NO = 'N'
    UNKNOWN = 'UN'
    SALES_AFFECTED_CHOICES = (
        (YES, 'yes'),
        (NO, 'no'),
        (UNKNOWN, 'unknown'),
    )

    summary = models.TextField(null=False, blank=False, max_length=3000)
    sales_affected_choice = models.CharField(choices=SALES_AFFECTED_CHOICES, max_length=2, default=UNKNOWN)
    sales_affected = models.TextField(max_length=3000, null=True, blank=True)
    systems_affected = models.ManyToManyField(System)
    communication_assignee = models.ForeignKey(USER_MODEL, related_name='comunicate_outages', on_delete=models.CASCADE)
    solution_assignee = models.ForeignKey(USER_MODEL, related_name='solves_outages', on_delete=models.CASCADE)
    created = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(USER_MODEL, related_name='outage_created', on_delete=models.CASCADE)
    started_at = models.DateTimeField(default=timezone.now)

    # Never set ETA manually. Use helper methods "set_eta" and "real_eta"
    # for proper representation.
    eta = models.IntegerField(null=False, blank=True, default=0)
    eta_last_modified = models.DateTimeField(null=True)

    class Meta:
        abstract = True

    @property
    def sales_has_been_affected(self):
        return self.sales_affected_choice == self.YES

    @property
    def sales_affected_choice_human(self):
        return [s[1] for s in self.SALES_AFFECTED_CHOICES if s[0] == self.sales_affected_choice][0]

    @property
    def systems_affected_human(self):
        return ', '.join([sys.name for sys in self.systems_affected.all()]) or 'N/A'

    @property
    def real_eta(self):
        """Get properly represented ETA.

        Adds difference between last eta modification and outage creation
        date in minutes to ETA.
        """
        if self.eta_last_modified and not self.eta_is_unknown:
            delta = self.eta_last_modified - self.created
            minutes, seconds = divmod(delta.seconds, 60)
            return minutes + self.eta, seconds

        return self.eta, 0

    @property
    def _eta_deadline(self):
        created = arrow.get(self.created)
        minutes, seconds = self.real_eta
        return created.shift(minutes=minutes, seconds=seconds)

    @property
    def eta_deadline(self):
        return self._eta_deadline.timestamp

    @property
    def eta_human_deadline(self):
        return self._eta_deadline.datetime

    @property
    def eta_is_unknown(self):
        return self.eta == 0

    @property
    def real_eta_in_minutes(self):
        return self.real_eta[0]

    @property
    def eta_remaining(self):
        """Calculate remaining ETA from now in minutes."""
        if self.eta_is_unknown:
            return ''
        deadline = self.eta_human_deadline
        if deadline < timezone.now():
            return 0

        delta = deadline - timezone.now()
        minutes, _ = divmod(delta.seconds, 60)
        return minutes

    @property
    def created_timestamp(self):
        return int(self.created.timestamp())


class Outage(AbstractOutage):

    def __str__(self):
        return f'Outage {self.id}'

    @property
    def is_resolved(self):
        try:
            if self.solution is not None:
                return self.solution
            return False
        except ObjectDoesNotExist:
            return False

    @property
    def resolved_on_time(self):
        now = arrow.utcnow()
        solution = self.is_resolved
        if solution:
            if solution.created > self.eta_human_deadline:
                return False
            return True

        if self.eta_human_deadline < now:
            return False
        return True

    def set_eta(self, eta):
        """Properly sets eta. Never change eta manually.

        This method will set eta and eta_last_modifie values.
        Both are needed for proper representation.
        """
        if not eta:
            # check because slack can return null
            eta = 0
        self.eta_last_modified = timezone.now()
        self.eta = eta

    def _make_assignee(self, user_last_name, column='solution_assignee'):
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
        self._make_assignee(user_last_name, column='communication_assignee')

    def add_affected_system(self, system_id):
        try:
            self.systems_affected.add(system_id)
            return True
        except IntegrityError:
            return False

    def remove_affected_system(self, system_id):
        try:
            if self.systems_affected.get(id=system_id):
                self.systems_affected.remove(system_id)
                return True
        except models.ObjectDoesNotExist:
            pass
        return False

    def add_notification(self, text, by_user):
        self.notifications.create(text=text, created_by=by_user)

    def get_involved_user_ids(self):
        """Return IDs of creater and assignees."""
        involved_users = [
            self.created_by.id,
            self.solution_assignee.id,
            self.communication_assignee.id,
        ]
        return involved_users

    def can_edit_outage(self, user_id):
        """Check if user is linked to outage."""
        return user_id in self.get_involved_user_ids()

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        change_desc = kwargs.pop('change_desc', None)
        modified_by = kwargs.pop('modified_by', None)
        self.summary = self.summary.strip()

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
        )
        history.systems_affected.set(self.systems_affected.all())
        history.save()

    class Meta:
        ordering = ['-pk']


class OutageHistory(AbstractOutage):
    modified_by = models.ForeignKey(USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    outage = models.ForeignKey(Outage, related_name='history_outage', on_delete=models.CASCADE)
    change_desc = models.TextField(null=True, blank=True, max_length=3000)
    timestamp = models.DateTimeField(auto_now_add=True)
    # name colisions
    created_by = models.ForeignKey(USER_MODEL, related_name='history_outage_created', on_delete=models.CASCADE)
    resolved_by = models.ForeignKey(USER_MODEL, related_name='history_outage_resolved', on_delete=models.CASCADE,
                                    null=True, blank=True)
    communication_assignee = models.ForeignKey(USER_MODEL, related_name='history_comunicate_outages',
                                               on_delete=models.CASCADE)
    solution_assignee = models.ForeignKey(USER_MODEL, related_name='history_solves_outages', on_delete=models.CASCADE)

    def __str__(self):
        return f'History Outage {self.id} for Outage {self.outage.id}'

    class Meta:
        ordering = ['-pk']


class AbstractSolution(models.Model):

    class Meta:
        abstract = True

    POSTMORTEM = 'PM'
    NONE = 'NO'
    OUTCOME_CHOICES = (
        (POSTMORTEM, 'Postmortem report'),
        (NONE, 'None'),
    )

    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(USER_MODEL, related_name='solution_created', on_delete=models.CASCADE, null=True,
                                   blank=True)
    summary = models.TextField(max_length=3000, null=True, blank=True)
    resolved_at = models.DateTimeField(default=timezone.now)
    solving_time = models.IntegerField(default=0)
    suggested_outcome = models.CharField(choices=OUTCOME_CHOICES, default=NONE, max_length=2)
    report_url = models.TextField(null=True, blank=True)
    report_title = models.TextField(null=True, blank=True)
    sales_affected = models.TextField(max_length=3000, null=True, blank=True)

    @property
    def suggested_outcome_human(self):
        return [c for k, c in self.OUTCOME_CHOICES if k == self.suggested_outcome][0]


class Solution(AbstractSolution):
    outage = models.OneToOneField(Outage, on_delete=models.CASCADE)

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
        minutes, _ = divmod(downtime.seconds, 60)
        return minutes

    def duration(self):
        downtime = self.downtime()
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
        if self.suggested_outcome == self.POSTMORTEM:
            return not self.report_url

    @property
    def full_report_url(self):
        if self.report_url and not self.report_url.startswith('http'):
            return f'https://{self.report_url}'
        return self.report_url

    def __str__(self):
        return f'Solution {self.pk}'

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        modified_by = kwargs.pop('modified_by', None)
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
            sales_affected=self.sales_affected,
        )

    class Meta:
        ordering = ['-pk']


class SolutionHistory(AbstractSolution):
    modified_by = models.ForeignKey(USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    # name clashes
    created_by = models.ForeignKey(USER_MODEL, related_name='history_solution_created',
                                   on_delete=models.CASCADE, null=True, blank=True)
    solution = models.ForeignKey(Solution, related_name='solution_history',
                                 on_delete=models.CASCADE)

    class Meta:
        ordering = ['-pk']


class Notification(models.Model):
    created = models.DateTimeField(default=timezone.now)
    text = models.TextField(null=False, blank=False)
    outage = models.ForeignKey(Outage, related_name='notifications', on_delete=models.CASCADE)
    created_by = models.ForeignKey(USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f'Notification {self.id} for Outage {self.outage.id}'

    class Meta:
        ordering = ['-pk']


class AbstractMonitor(models.Model):
    LOW = 'LO'
    MEDIUM = 'ME'
    HIGH = 'HI'
    UNDEFINED = 'UN'

    SEVERITY_CHOICES = (
        (UNDEFINED, 'undefined'),
        (LOW, 'low'),
        (MEDIUM, 'medium'),
        (HIGH, 'high'),
    )

    DATADOG = 'DD'
    PINGDOM = 'PD'

    MONITORING_SYSTEM_CHOICES = (
        (UNDEFINED, 'Undefined'),
        (DATADOG, 'Datadog'),
        (PINGDOM, 'Pingdom'),
    )

    monitoring_system = models.CharField(max_length=2,
                                         choices=MONITORING_SYSTEM_CHOICES,
                                         default=UNDEFINED)
    external_id = models.CharField(blank=False, null=False, max_length=100)
    created = models.DateTimeField(default=timezone.now)
    link = models.CharField(max_length=200)
    severity = models.CharField(choices=SEVERITY_CHOICES, default=UNDEFINED, max_length=2)
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
            logger.info(f'{alert} already exists!')


class Monitor(AbstractMonitor):
    class Meta:
        unique_together = ('monitoring_system', 'external_id')

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        modified_by = kwargs.pop('modified_by', None)

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
    modified_by = models.ForeignKey(USER_MODEL, blank=True, null=True, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    monitor = models.ForeignKey(Monitor, blank=True, null=True, related_name='history', on_delete=models.CASCADE)
    external_id = models.CharField(blank=False, null=False, max_length=100)


class Alert(models.Model):
    UNDEFINED = 'UN'
    WARNING = 'WA'
    CRITICAL = 'CR'

    TYPE_CHOICES = (
        (UNDEFINED, 'undefined'),
        (WARNING, 'warning'),
        (CRITICAL, 'critical'),
    )

    created = models.DateTimeField(auto_now_add=True)
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE)
    ts = models.DateTimeField(null=True, default=None)
    alert_type = models.CharField(blank=False, null=False, choices=TYPE_CHOICES, default=UNDEFINED, max_length=2)

    class Meta:
        unique_together = ('monitor', 'ts')

    def __str__(self):
        return f'Alert monitor={self.monitor.external_id} ts={self.ts}'
