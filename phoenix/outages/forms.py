from django.contrib.auth import get_user_model
from django.forms import DateTimeField, DateTimeInput, ModelChoiceField, ModelForm

from ..core.models import Monitor, Outage, Solution


class UserChoiceField(ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.email or obj.username


class OutageBaseForm(ModelForm):
    class Meta:
        model = Outage
        fields = ['summary', 'sales_affected_choice', 'lost_bookings', 'impact_on_turnover', 'systems_affected', 'eta']
        labels = {
            'eta': "ETA in minutes. Leave empty if unknown.",
        }


class OutageCreateForm(OutageBaseForm):
    class Meta(OutageBaseForm.Meta):
        fields = OutageBaseForm.Meta.fields + ['announce_on_slack']


class OutageUpdateForm(OutageBaseForm):
    communication_assignee = UserChoiceField(
        queryset=get_user_model().objects.exclude(email__isnull=True).exclude(email__exact=''))
    solution_assignee = UserChoiceField(
        queryset=get_user_model().objects.exclude(email__isnull=True).exclude(email__exact=''))

    def save(self, commit=True):
        m = super().save(commit=False)
        m.solution_assignee = self.cleaned_data['solution_assignee']
        m.communication_assignee = self.cleaned_data['communication_assignee']
        m.eta_last_modified = self.eta_last_modified

        if commit:
            m.save(modified_by=self.modified_by)
        return m


class SolutionCreateForm(ModelForm):
    class Meta:
        model = Solution
        fields = ['summary', 'resolved_at', 'suggested_outcome', 'report_url']
        field_classes = {
            'resolved_at': DateTimeField,
        }
        widgets = {
            'resolved_at': DateTimeInput(),
        }
        labels = {
            'report_url': 'Report URL',
        }


class MonitorUpdate(ModelForm):
    class Meta:
        model = Monitor
        fields = ['created_by', 'name', 'severity', 'description']

    def save(self, commit=True):
        m = super().save(commit=False)

        if commit:
            m.save(modified_by=self.modified_by)
        return m
