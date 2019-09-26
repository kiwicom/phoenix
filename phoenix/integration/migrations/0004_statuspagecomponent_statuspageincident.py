# Generated by Django 2.2 on 2019-06-12 07:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("integration", "0003_auto_20181204_1136")]

    operations = [
        migrations.CreateModel(
            name="StatusPageIncident",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("status_page_id", models.CharField(max_length=100)),
                ("url", models.CharField(blank=True, max_length=1000, null=True)),
                ("edit_url", models.CharField(blank=True, max_length=1000, null=True)),
                (
                    "outage",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_page_incident",
                        to="core.Outage",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="StatusPageComponent",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=1000)),
                ("status_page_id", models.CharField(max_length=100)),
                (
                    "systems_affected",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_page_components",
                        to="core.System",
                    ),
                ),
            ],
        ),
    ]