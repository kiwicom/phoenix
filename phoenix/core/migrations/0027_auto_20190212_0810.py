# Generated by Django 2.1.3 on 2019-02-12 08:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("core", "0026_auto_20190311_0952")]

    operations = [
        migrations.RenameField(
            model_name="outage",
            old_name="systems_affected",
            new_name="systems_affected_bck",
        ),
        migrations.RenameField(
            model_name="outagehistory",
            old_name="systems_affected",
            new_name="systems_affected_bck",
        ),
        migrations.AddField(
            model_name="outage",
            name="systems_affected",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="systems_outage",
                to="core.System",
            ),
        ),
        migrations.AddField(
            model_name="outagehistory",
            name="systems_affected",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="systems_outagehistory",
                to="core.System",
            ),
        ),
    ]