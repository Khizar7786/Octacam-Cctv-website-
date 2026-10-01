from django.db import migrations, models


def copy_slot_times(apps, schema_editor):
    slots = apps.get_model("surveys", "SurveySlot")
    bookings = apps.get_model("surveys", "SurveyBooking")
    database = schema_editor.connection.alias
    for slot in slots.objects.using(database).iterator():
        bookings.objects.using(database).filter(slot_id=slot.pk).update(
            scheduled_starts_at=slot.starts_at, scheduled_ends_at=slot.ends_at,
        )


class Migration(migrations.Migration):
    dependencies = [("surveys", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="surveybooking", name="version", field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="surveybooking", name="scheduled_starts_at", field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="surveybooking", name="scheduled_ends_at", field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(copy_slot_times, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="surveybooking", name="scheduled_starts_at", field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name="surveybooking", name="scheduled_ends_at", field=models.DateTimeField(),
        ),
        migrations.AddConstraint(
            model_name="surveybooking",
            constraint=models.CheckConstraint(
                condition=models.Q(scheduled_ends_at__gt=models.F("scheduled_starts_at")),
                name="survey_booking_end_after_start",
            ),
        ),
    ]
