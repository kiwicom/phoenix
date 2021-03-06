# Generated by Django 2.0.5 on 2018-06-26 09:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("core", "0002_auto_20180620_1508")]

    operations = [
        migrations.CreateModel(
            name="Alert",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "alert_type",
                    models.CharField(
                        choices=[
                            ("UN", "undefined"),
                            ("WA", "warning"),
                            ("CR", "critical"),
                        ],
                        default="UN",
                        max_length=2,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Monitor",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("datadog_id", models.CharField(max_length=100, unique=True)),
                ("link", models.CharField(max_length=200)),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("UN", "undefined"),
                            ("LO", "low"),
                            ("ME", "medium"),
                            ("HI", "high"),
                        ],
                        default="UN",
                        max_length=2,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="alert",
            name="monitor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="core.Monitor"
            ),
        ),
    ]
