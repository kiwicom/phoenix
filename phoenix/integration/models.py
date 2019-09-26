from django.db import models

from ..core.models import Outage, System


class GoogleGroup(models.Model):
    name = models.CharField(max_length=1000, null=False, blank=False)
    key = models.CharField(max_length=1000, null=False, blank=False, unique=True)
    is_allowed = models.BooleanField(default=True, blank=True)

    def __str__(self):
        return f"GoogleGroup({self.id}) - {self.name}"


class StatusPageComponent(models.Model):
    name = models.CharField(max_length=1000, null=False, blank=False)
    status_page_id = models.CharField(max_length=100, null=False, blank=False)
    systems_affected = models.ForeignKey(
        System,
        related_name="status_page_components",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"StatusPageComponent({self.id}): {self.name}"


class StatusPageIncident(models.Model):
    status_page_id = models.CharField(max_length=100, null=False, blank=False)
    url = models.CharField(max_length=1000, null=True, blank=True)
    edit_url = models.CharField(max_length=1000, null=True, blank=True)
    outage = models.OneToOneField(
        Outage, related_name="status_page_incident", on_delete=models.CASCADE
    )

    def __str__(self):
        return f"StatusPageIncident({self.id})"
