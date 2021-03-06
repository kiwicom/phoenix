# Generated by Django 2.0.5 on 2018-07-03 10:06

from django.db import migrations, models


def fix_monitoring_system(apps, schema_editor):
    Monitor = apps.get_model("core", "Monitor")
    for monitor in Monitor.objects.all():
        if monitor.monitoring_system == "UN":
            monitor.monitoring_system = "DD"
            monitor.save()
    MonitorHistory = apps.get_model("core", "MonitorHistory")
    for monitor in MonitorHistory.objects.all():
        if monitor.monitoring_system == "UN":
            monitor.monitoring_system = "DD"
            monitor.save()


class Migration(migrations.Migration):

    dependencies = [("core", "0005_auto_20180703_0844")]

    operations = [
        migrations.AddField(
            model_name="monitor",
            name="monitoring_system",
            field=models.CharField(
                choices=[("UN", "Undefined"), ("DD", "Datadog"), ("PD", "Pingdom")],
                default="UN",
                max_length=2,
            ),
        ),
        migrations.AddField(
            model_name="monitorhistory",
            name="monitoring_system",
            field=models.CharField(
                choices=[("UN", "Undefined"), ("DD", "Datadog"), ("PD", "Pingdom")],
                default="UN",
                max_length=2,
            ),
        ),
        migrations.RunPython(fix_monitoring_system),
        migrations.AlterField(
            model_name="monitor",
            name="external_id",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterUniqueTogether(
            name="monitor", unique_together={("monitoring_system", "external_id")}
        ),
    ]
