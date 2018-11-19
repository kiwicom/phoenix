# Generated by Django 2.0.5 on 2018-10-23 06:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_auto_20180906_1153'),
    ]

    operations = [
        migrations.AddField(
            model_name='outage',
            name='sales_affected_choice',
            field=models.CharField(choices=[('Y', 'yes'), ('N', 'no'), ('UN', 'unknown')], default='UN', max_length=2),
        ),
        migrations.AddField(
            model_name='outagehistory',
            name='sales_affected_choice',
            field=models.CharField(choices=[('Y', 'yes'), ('N', 'no'), ('UN', 'unknown')], default='UN', max_length=2),
        ),
    ]
