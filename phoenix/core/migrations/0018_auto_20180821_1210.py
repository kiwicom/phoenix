# Generated by Django 2.0.5 on 2018-08-21 12:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_auto_20180820_1110'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='image_48_url',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='slack_username',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
    ]
