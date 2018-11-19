from django.db import models


class GoogleGroup(models.Model):
    name = models.CharField(max_length=1000, null=False, blank=False)
    key = models.CharField(max_length=1000, null=False, blank=False, unique=True)
    is_allowed = models.BooleanField(default=True, blank=True)

    def __str__(self):
        return f"GoogleGroup({self.id}) - {self.name}"
