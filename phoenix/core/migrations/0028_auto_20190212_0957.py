# Generated by Django 2.1.3 on 2019-02-12 09:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_auto_20190212_0810'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='outage',
            name='systems_affected_bck',
        ),
        migrations.RemoveField(
            model_name='outagehistory',
            name='systems_affected_bck',
        ),
    ]
