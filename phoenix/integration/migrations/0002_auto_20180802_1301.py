# Generated by Django 2.0.5 on 2018-08-02 13:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integration', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='googlegroup',
            name='key',
            field=models.CharField(max_length=1000, unique=True),
        ),
    ]
