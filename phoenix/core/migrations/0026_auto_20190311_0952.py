# Generated by Django 2.1.3 on 2019-03-11 09:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0025_auto_20190306_0759")]

    operations = [
        migrations.RemoveField(model_name="solution", name="sales_affected"),
        migrations.RemoveField(model_name="solutionhistory", name="sales_affected"),
        migrations.AddField(
            model_name="outage",
            name="impact_on_turnover",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="outage",
            name="lost_bookings",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="outagehistory",
            name="impact_on_turnover",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="outagehistory",
            name="lost_bookings",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
