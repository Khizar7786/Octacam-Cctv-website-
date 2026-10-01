import uuid
from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.surveys.tests.test_slot_api import future_start


class SurveyBookingMigrationTests(TransactionTestCase):
    def test_existing_bookings_keep_details_and_receive_time_snapshots(self):
        old_target = [("surveys", "0001_initial")]
        new_target = [("surveys", "0002_booking_management")]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(old_target)
            old_apps = executor.loader.project_state(old_target).apps
            slot_model = old_apps.get_model("surveys", "SurveySlot")
            booking_model = old_apps.get_model("surveys", "SurveyBooking")
            start = future_start()
            slot = slot_model.objects.create(starts_at=start, ends_at=start + timedelta(hours=1), capacity=1)
            identifiers = []
            for status in ("confirmed", "completed", "cancelled"):
                booking = booking_model.objects.create(
                    slot_id=slot.pk, reference=f"OCS-{status}", customer_name="Test Customer",
                    customer_email="migration@example.com", customer_phone="test-phone",
                    site_address_line1="Test address", site_city="Lahore", needs_description="Test needs",
                    internal_notes="Private note", status=status, idempotency_key=uuid.uuid4(), request_fingerprint="a" * 64,
                )
                identifiers.append((booking.pk, booking.public_id, booking.guest_link_nonce, status))
            executor = MigrationExecutor(connection)
            executor.migrate(new_target)
            new_model = executor.loader.project_state(new_target).apps.get_model("surveys", "SurveyBooking")
            for pk, public_id, nonce, status in identifiers:
                booking = new_model.objects.get(pk=pk)
                self.assertEqual((booking.scheduled_starts_at, booking.scheduled_ends_at), (start, start + timedelta(hours=1)))
                self.assertEqual((booking.public_id, booking.guest_link_nonce, booking.status), (public_id, nonce, status))
                self.assertEqual((booking.internal_notes, booking.version), ("Private note", 0))
        finally:
            MigrationExecutor(connection).migrate(new_target)
