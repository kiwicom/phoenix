# Generated by Django 2.1.3 on 2019-02-02 19:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0022_auto_20181122_0952")]

    operations = [
        migrations.AddField(
            model_name="solution",
            name="report_title",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solutionhistory",
            name="report_title",
            field=models.TextField(blank=True, null=True),
        ),
    ]
