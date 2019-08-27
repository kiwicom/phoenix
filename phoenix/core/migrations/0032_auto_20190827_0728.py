# Generated by Django 2.2 on 2019-08-27 07:28

from django.db import migrations, models


def map_eta(eta):
    if eta < 30:
        new_eta = "<30m"
    elif eta < 120:
        new_eta = "<2h"
    elif eta < 480:
        new_eta = "<8h"
    elif eta < 1440:
        new_eta = "<24h"
    else:
        new_eta = ">24h"
    return new_eta


def transform_previous_eta_values(apps, schema_editor):
    Outage = apps.get_model("core", "Outage")
    OutageHistory = apps.get_model("core", "OutageHistory")
    for outage in Outage.objects.all():
        eta = int(outage.eta)
        outage.eta = map_eta(eta)
        outage.save()
    for outage_history in OutageHistory.objects.all():
        eta = int(outage_history.eta)
        outage_history.eta = map_eta(eta)
        outage_history.save()


class Migration(migrations.Migration):

    dependencies = [("core", "0031_auto_20190612_1001")]

    operations = [
        migrations.RemoveField(model_name="outage", name="prompt_active"),
        migrations.RemoveField(model_name="outage", name="prompt_for_eta_update"),
        migrations.AddField(
            model_name="outage",
            name="lost_bookings_choice",
            field=models.CharField(
                choices=[
                    ("0%", "0%"),
                    ("<30%", "<30%"),
                    ("<60%", "<60%"),
                    ("<100%", "<100%"),
                    ("100%", "100%"),
                ],
                default=0,
                max_length=5,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="outagehistory",
            name="lost_bookings_choice",
            field=models.CharField(
                choices=[
                    ("0%", "0%"),
                    ("<30%", "<30%"),
                    ("<60%", "<60%"),
                    ("<100%", "<100%"),
                    ("100%", "100%"),
                ],
                default=0,
                max_length=5,
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="outage",
            name="eta",
            field=models.CharField(
                choices=[
                    ("<30m", "<30m"),
                    ("<2h", "<2h"),
                    ("<8h", "<8h"),
                    ("<24h", "<24h"),
                    (">24h", ">24h"),
                ],
                max_length=6,
            ),
        ),
        migrations.AlterField(
            model_name="outage",
            name="lost_bookings",
            field=models.TextField(blank=True, max_length=3000, null=True),
        ),
        migrations.AlterField(
            model_name="outagehistory",
            name="eta",
            field=models.CharField(
                choices=[
                    ("<30m", "<30m"),
                    ("<2h", "<2h"),
                    ("<8h", "<8h"),
                    ("<24h", "<24h"),
                    (">24h", ">24h"),
                ],
                max_length=6,
            ),
        ),
        migrations.AlterField(
            model_name="outagehistory",
            name="lost_bookings",
            field=models.TextField(blank=True, max_length=3000, null=True),
        ),
        migrations.RunPython(transform_previous_eta_values),
    ]