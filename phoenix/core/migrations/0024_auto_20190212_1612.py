# Generated by Django 2.1.3 on 2019-02-12 16:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0023_auto_20190202_1935")]

    operations = [
        migrations.AddField(
            model_name="outage",
            name="announce_on_slack",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="outagehistory",
            name="announce_on_slack",
            field=models.BooleanField(default=True),
        ),
    ]
