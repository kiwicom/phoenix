# Generated by Django 2.0.5 on 2018-08-02 13:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0013_merge_20180730_1002")]

    operations = [
        migrations.AlterField(
            model_name="solution",
            name="suggested_outcome",
            field=models.CharField(
                choices=[("PM", "Postmortem report"), ("NO", "None")],
                default="NO",
                max_length=2,
            ),
        )
    ]
