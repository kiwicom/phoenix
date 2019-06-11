# Generated by Django 2.0.5 on 2018-06-27 12:08

from django.db import migrations, models


def fix_ts(apps, schema_editor):
    Alert = apps.get_model("core", "Alert")
    for alert in Alert.objects.all():
        if alert.ts is None:
            alert.ts = alert.created
            alert.save()


class Migration(migrations.Migration):

    dependencies = [("core", "0003_auto_20180626_0954")]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="ts",
            field=models.DateTimeField(default=None, null=True),
        ),
        migrations.RunPython(fix_ts),
        migrations.AlterUniqueTogether(
            name="alert", unique_together={("monitor", "ts")}
        ),
    ]
