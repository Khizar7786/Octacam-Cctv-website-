import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from apps.catalog.models import Brand, Category, InventoryMovement, Product
from apps.communications.models import EmailOutbox
from apps.communications.services import process_email_batch
from apps.orders.fulfillment_services import cancel_order
from apps.orders.models import Order, OrderItem
from apps.orders.services import create_quote, order_survey_key
from apps.orders.tests.test_checkout_api import CHECKOUT_SETTINGS, cart, make_product, place_data
from apps.surveys.management_services import reschedule_survey, transition_survey
from apps.surveys.models import SurveyBooking
from apps.surveys.tests.test_booking_api import booking_data, make_slot
from apps.surveys.tests.test_slot_api import make_booking


PLACE_URL = "/api/v1/checkout/place/"
SURVEY_SETTINGS = override_settings(SURVEY_LAHORE_SERVICE_AREAS='["Approved test area"]')


def survey_data(slot):
    return {field: value for field, value in booking_data(slot).items() if not field.startswith("customer_")}


def combined_data(product, slot):
    return {**place_data(product, create_quote(cart(product))["quote_token"]), "survey": survey_data(slot)}


@CHECKOUT_SETTINGS
@SURVEY_SETTINGS
class CombinedCheckoutApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = make_product()
        cls.customer = get_user_model().objects.create_user(
            email="combined-customer@example.com", password="test-password", full_name="Customer",
        )
        cls.staff = get_user_model().objects.create_user(
            email="combined-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.slot = make_slot()
        self.data = combined_data(self.product, self.slot)
        self.key = uuid.uuid4()

    def place(self, data=None):
        return self.client.post(PLACE_URL, self.data if data is None else data, format="json", HTTP_IDEMPOTENCY_KEY=str(self.key))

    def assert_no_purchase(self):
        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.assertFalse(InventoryMovement.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(EmailOutbox.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)

    def test_guest_combined_receipt_independent_addresses_tracking_and_both_emails(self):
        # Lahore survey eligibility follows the site address, even when equipment ships elsewhere.
        data = {**self.data, "delivery_city": "Karachi", "delivery_province": "Sindh"}
        quoted = self.client.post("/api/v1/checkout/quote/", {
            "items": data["items"], "delivery_city": data["delivery_city"], "delivery_province": data["delivery_province"],
        }, format="json")
        self.assertEqual(quoted.status_code, 200, quoted.data)
        data["quote_token"] = quoted.data["quote_token"]
        receipt = self.place(data)
        self.assertEqual(receipt.status_code, 201, receipt.data)
        order, booking = Order.objects.get(), SurveyBooking.objects.get()
        self.assertEqual(booking.related_order_id, order.pk)
        self.assertEqual(booking.idempotency_key, order_survey_key(order))
        self.assertNotEqual(booking.idempotency_key, order.idempotency_key)
        self.assertEqual(booking.status, "confirmed")
        self.assertEqual((booking.customer_name, booking.customer_email, booking.customer_phone),
                         (order.customer_name, order.customer_email, order.customer_phone))
        self.assertIsNone(order.user_id)
        self.assertIsNone(booking.user_id)
        self.assertEqual((order.delivery_city, booking.site_city), ("Karachi", "Lahore"))
        self.assertNotEqual(order.delivery_address_line1, booking.site_address_line1)
        self.assertEqual(receipt.data["grand_total"], quoted.data["grand_total"])
        self.assertEqual(receipt.data["payment_method"], "COD")
        self.assertEqual(receipt.data["payment_status"], "uncollected")
        self.assertEqual(receipt.data["survey"]["reference"], booking.reference)
        self.assertNotEqual(booking.reference, order.reference)
        self.assertEqual(receipt.data["survey"]["booking_fee"], "0.00")
        self.assertIn("Installation is quoted", receipt.data["survey"]["installation_notice"])
        self.assertEqual(receipt["Cache-Control"], "private, no-store")
        self.assertEqual(receipt["Referrer-Policy"], "no-referrer")
        self.assertIn("noindex", receipt["X-Robots-Tag"])
        for secret in ("internal_notes", "idempotency_key", "guest_link_nonce", "request_fingerprint"):
            self.assertNotIn(secret, receipt.data["survey"])
        order_path = urlsplit(receipt.data["guest_tracking_url"]).path
        survey_path = urlsplit(receipt.data["survey"]["guest_tracking_url"]).path
        order_tracking, survey_tracking = self.client.get(order_path), self.client.get(survey_path)
        self.assertEqual((order_tracking.status_code, survey_tracking.status_code), (200, 200))
        self.assertNotIn("survey", order_tracking.data)
        self.assertNotIn(order.reference, str(survey_tracking.data))
        self.assertNotIn(booking.site_address_line1, str(survey_tracking.data))
        self.assertEqual((OrderItem.objects.count(), InventoryMovement.objects.count(), AuditEvent.objects.count()), (1, 1, 2))
        self.assertEqual(set(EmailOutbox.objects.values_list("event_type", flat=True)), {"ORDER_PLACED", "SURVEY_CONFIRMED"})
        self.assertEqual(process_email_batch(), ["sent", "sent"])
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(order.reference, mail.outbox[0].subject)
        self.assertIn(booking.reference, mail.outbox[1].subject)
        self.assertIn(receipt.data["survey"]["guest_tracking_url"], mail.outbox[1].body)

    def test_signed_in_combined_resources_belong_to_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.customer).access_token}")
        receipt = self.place()
        self.assertEqual(receipt.status_code, 201, receipt.data)
        self.assertEqual(Order.objects.get().user_id, self.customer.pk)
        self.assertEqual(SurveyBooking.objects.get().user_id, self.customer.pk)
        self.assertIsNone(receipt.data["guest_tracking_url"])
        self.assertIsNone(receipt.data["survey"]["guest_tracking_url"])
        self.assertEqual(self.client.get("/api/v1/account/orders/").data["count"], 1)

    def test_retry_after_uncertain_response_recovers_both_without_current_configuration(self):
        first = self.place()
        self.assertEqual(first.status_code, 201, first.data)
        self.slot.is_open = False
        self.slot.save(update_fields=["is_open"])
        with override_settings(CHECKOUT_SHIPPING_FEE=None, SURVEY_LAHORE_SERVICE_AREAS=None):
            with patch("apps.orders.services._read_quote_token", side_effect=AssertionError("Do not revalidate a successful submission")):
                replay = self.place()
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(replay.data, first.data)
        self.assertEqual((Order.objects.count(), SurveyBooking.objects.count(), OrderItem.objects.count(),
                          InventoryMovement.objects.count(), AuditEvent.objects.count(), EmailOutbox.objects.count()), (1, 1, 1, 1, 2, 2))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 1)

    def test_key_reuse_with_changed_survey_opt_in_or_identity_conflicts(self):
        self.assertEqual(self.place().status_code, 201)
        alternative = make_slot(days=8)
        for data in (
            {**self.data, "survey": {**self.data["survey"], "slot_public_id": str(alternative.public_id)}},
            {**self.data, "survey": {**self.data["survey"], "site_address_line1": "Different site"}},
            {**self.data, "survey": {**self.data["survey"], "needs_description": "Different needs"}},
            {**self.data, "survey": None},
            {field: value for field, value in self.data.items() if field != "survey"},
        ):
            response = self.place(data)
            self.assertEqual(response.status_code, 409, response.data)
            self.assertEqual(response.data["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.client.force_authenticate(user=self.customer)
        self.assertEqual(self.place().data["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual((Order.objects.count(), SurveyBooking.objects.count(), EmailOutbox.objects.count()), (1, 1, 2))

    def test_closed_past_missing_and_full_slots_roll_back_every_order_effect(self):
        closed, past = make_slot(days=8), make_slot(days=-1)
        closed.is_open = False
        closed.save(update_fields=["is_open"])
        make_booking(self.slot, status="completed")
        for slot_id in (closed.public_id, past.public_id, self.slot.public_id, uuid.uuid4()):
            with self.subTest(slot_id=slot_id):
                response = self.place({**self.data, "survey": {**self.data["survey"], "slot_public_id": str(slot_id)}})
                self.assertEqual(response.status_code, 409, response.data)
                self.assertEqual(response.data["error"]["code"], "SURVEY_SLOT_UNAVAILABLE")
                self.assertIsNone(response.data["current_quote"])
                self.assertEqual(response["Cache-Control"], "private, no-store")
                self.assert_no_purchase()
                self.assertEqual(SurveyBooking.objects.count(), 1)

    def test_invalid_site_and_nested_fields_roll_back_and_give_field_paths(self):
        for changes, field in (
            ({"site_city": "Karachi"}, "site_city"), ({"site_area": "Outside test coverage"}, "site_area"),
            ({"site_address_line1": ""}, "site_address_line1"), ({"slot_public_id": "invalid"}, "slot_public_id"),
            ({"related_order": "forged"}, "related_order"), ({"customer_email": "forged@example.com"}, "customer_email"),
            ({"idempotency_key": str(uuid.uuid4())}, "idempotency_key"), ({"booking_fee": "500.00"}, "booking_fee"),
        ):
            with self.subTest(field=field):
                response = self.place({**self.data, "survey": {**self.data["survey"], **changes}})
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(f"survey.{field}", response.data["error"]["fields"])
                self.assert_no_purchase()
                self.assertFalse(SurveyBooking.objects.exists())

    def test_unconfigured_coverage_blocks_combined_but_not_equipment_only(self):
        with override_settings(SURVEY_LAHORE_SERVICE_AREAS=None):
            response = self.place()
            self.assertEqual(response.status_code, 503, response.data)
            self.assertEqual(response.data["error"]["code"], "SURVEY_NOT_CONFIGURED")
            self.assert_no_purchase()
            self.assertFalse(SurveyBooking.objects.exists())
            equipment_data = {field: value for field, value in self.data.items() if field != "survey"}
            receipt = self.place(equipment_data)
            self.assertEqual(receipt.status_code, 201, receipt.data)
            self.assertIsNone(receipt.data["survey"])
            replay = self.place({**equipment_data, "survey": None})
            self.assertEqual(replay.status_code, 200, replay.data)
            self.assertEqual(replay.data, receipt.data)

    def test_failed_slot_submission_can_be_corrected_without_partial_or_duplicate_creation(self):
        self.slot.is_open = False
        self.slot.save(update_fields=["is_open"])
        self.assertEqual(self.place().status_code, 409)
        self.assert_no_purchase()
        destination = make_slot(days=8)
        data = {**self.data, "survey": survey_data(destination)}
        self.assertEqual(self.place(data).status_code, 201)
        self.assertEqual(self.place(data).status_code, 200)
        self.assertEqual((Order.objects.count(), SurveyBooking.objects.count(), InventoryMovement.objects.count()), (1, 1, 1))

    def test_changed_quote_requires_review_and_does_not_consume_survey_capacity(self):
        Product.objects.filter(pk=self.product.pk).update(sale_price="800.00")
        response = self.place()
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["error"]["code"], "CHECKOUT_CHANGED")
        self.assert_no_purchase()
        self.assertFalse(SurveyBooking.objects.exists())
        reviewed = {**self.data, "quote_token": response.data["current_quote"]["quote_token"]}
        receipt = self.place(reviewed)
        self.assertEqual(receipt.status_code, 201, receipt.data)
        self.assertEqual(receipt.data["grand_total"], response.data["current_quote"]["grand_total"])

    def test_survey_audit_or_outbox_persistence_failure_rolls_back_both_resources(self):
        for target in ("apps.surveys.booking_services.enqueue_email", "apps.surveys.booking_services.record_audit_event"):
            with patch(target, side_effect=RuntimeError("persistence offline")):
                with self.assertRaises(RuntimeError):
                    self.place()
            self.assert_no_purchase()
            self.assertFalse(SurveyBooking.objects.exists())
        self.assertEqual(self.place().status_code, 201)

    def test_email_delivery_failure_does_not_undo_combined_confirmation(self):
        receipt = self.place()
        self.assertEqual(receipt.status_code, 201, receipt.data)
        with patch("apps.communications.services.deliver_email", side_effect=OSError("SMTP offline")):
            self.assertEqual(process_email_batch(), ["failed", "failed"])
        self.assertEqual((Order.objects.count(), SurveyBooking.objects.count(), InventoryMovement.objects.count()), (1, 1, 1))
        self.assertEqual(set(EmailOutbox.objects.values_list("status", flat=True)), {"failed"})
        replay = self.place()
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(replay.data, receipt.data)

    def test_order_cancellation_does_not_cancel_survey_and_retry_does_not_recreate_either(self):
        self.assertEqual(self.place().status_code, 201)
        order, booking = Order.objects.get(), SurveyBooking.objects.get()
        cancel_order(public_id=order.public_id, expected_version=0, reason="Customer requested through support", actor=self.staff)
        booking.refresh_from_db()
        self.assertEqual(booking.status, "confirmed")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)
        reschedule_survey(public_id=booking.public_id, slot_public_id=make_slot(days=8).public_id, expected_version=0, actor=self.staff)
        receipt = self.place()
        self.assertEqual(receipt.status_code, 200, receipt.data)
        self.assertEqual(receipt.data["status"], "cancelled")
        self.assertEqual(receipt.data["survey"]["status"], "confirmed")
        self.assertEqual(receipt.data["survey"]["reference"], booking.reference)
        self.assertEqual((Order.objects.count(), SurveyBooking.objects.count(), InventoryMovement.objects.count()), (1, 1, 2))

    def test_survey_cancellation_does_not_change_order_or_restore_equipment_stock(self):
        self.assertEqual(self.place().status_code, 201)
        order, booking = Order.objects.get(), SurveyBooking.objects.get()
        transition_survey(public_id=booking.public_id, expected_version=0, status="cancelled", actor=self.staff)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual((order.status, order.payment_status, self.product.stock_quantity), ("placed", "uncollected", 1))
        replay = self.place()
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(replay.data["survey"]["status"], "cancelled")
        self.assertEqual((Order.objects.count(), SurveyBooking.objects.count(), InventoryMovement.objects.count()), (1, 1, 1))

    def test_standalone_key_cannot_be_reused_to_attach_or_recover_a_combined_booking(self):
        standalone = self.client.post("/api/v1/surveys/bookings/", booking_data(make_slot(days=8)),
                                      format="json", HTTP_IDEMPOTENCY_KEY=str(self.key))
        self.assertEqual(standalone.status_code, 201, standalone.data)
        self.assertEqual(self.place().status_code, 201)
        order = Order.objects.get()
        linked = SurveyBooking.objects.get(related_order=order)
        separate = SurveyBooking.objects.get(public_id=standalone.data["public_id"])
        self.assertIsNone(separate.related_order_id)
        forged_replay = self.client.post("/api/v1/surveys/bookings/", {
            **self.data["survey"], **{field: self.data[field] for field in ("customer_name", "customer_email", "customer_phone")},
        }, format="json", HTTP_IDEMPOTENCY_KEY=str(linked.idempotency_key))
        self.assertEqual(forged_replay.status_code, 409, forged_replay.data)
        self.assertEqual(forged_replay.data["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(SurveyBooking.objects.count(), 2)


@CHECKOUT_SETTINGS
@SURVEY_SETTINGS
class CombinedCheckoutRaceTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.product = make_product()
        # Separate parents ensure competition reaches the slot lock, without sharing product/taxonomy locks.
        brand = Brand.objects.create(name="Other test brand", slug="other-test-brand")
        category = Category.objects.create(name="Other test cameras", slug="other-test-cameras")
        self.other_product = Product.objects.create(
            brand=brand, category=category, name="Other test camera", sku="COMBINED-2", slug="combined-camera-2",
            short_description="Camera", full_description="Camera", regular_price="1000.00", stock_quantity=2, is_published=True,
        )
        self.slot = make_slot()
        self.data = combined_data(self.product, self.slot)
        self.other_data = combined_data(self.other_product, self.slot)

    def place(self, data, key):
        return APIClient().post(PLACE_URL, data, format="json", HTTP_IDEMPOTENCY_KEY=str(key))

    def race(self, first_call, second_call):
        written, release, started, done = (Event() for _ in range(4))

        def first():
            close_old_connections()
            try:
                with transaction.atomic():
                    response = first_call()
                    written.set()
                    if not release.wait(10):
                        raise AssertionError("Timed out releasing combined checkout")
                    return response.status_code, response.data
            finally:
                close_old_connections()

        def second():
            close_old_connections()
            try:
                started.set()
                response = second_call()
                return response.status_code, response.data
            finally:
                done.set()
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(first)
            try:
                self.assertTrue(written.wait(10))
                second_future = pool.submit(second)
                self.assertTrue(started.wait(10))
                self.assertFalse(done.wait(0.2), "Second request bypassed the product/slot/idempotency lock")
            finally:
                release.set()
            return first_future.result(timeout=10), second_future.result(timeout=10)

    def assert_one_combined_submission(self):
        self.assertEqual((Order.objects.count(), SurveyBooking.objects.count(), OrderItem.objects.count(),
                          InventoryMovement.objects.count(), AuditEvent.objects.count(), EmailOutbox.objects.count()), (1, 1, 1, 1, 2, 2))

    def test_two_combined_requests_compete_for_final_slot_with_no_loser_order_or_stock_effect(self):
        first, second = self.race(lambda: self.place(self.data, uuid.uuid4()), lambda: self.place(self.other_data, uuid.uuid4()))
        self.assertEqual((first[0], second[0]), (201, 409))
        self.assertEqual(second[1]["error"]["code"], "SURVEY_SLOT_UNAVAILABLE")
        self.assert_one_combined_submission()
        self.other_product.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock_quantity, self.other_product.stock_quantity), (1, 2))

    def test_same_key_concurrent_retry_returns_both_original_receipts(self):
        key = uuid.uuid4()
        first, second = self.race(lambda: self.place(self.data, key), lambda: self.place(self.data, key))
        self.assertEqual((first[0], second[0]), (201, 200))
        self.assertEqual(first[1], second[1])
        self.assert_one_combined_submission()

    def test_same_key_different_products_and_slots_cannot_create_second_resource_pair(self):
        key = uuid.uuid4()
        alternative = make_slot(days=8)
        other_data = {**self.other_data, "survey": survey_data(alternative)}
        first, second = self.race(lambda: self.place(self.data, key), lambda: self.place(other_data, key))
        self.assertEqual((first[0], second[0]), (201, 409))
        self.assertEqual(second[1]["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assert_one_combined_submission()
        self.other_product.refresh_from_db()
        self.assertEqual(self.other_product.stock_quantity, 2)
        self.assertEqual(alternative.bookings.count(), 0)

    def test_last_equipment_unit_race_cannot_create_losing_survey(self):
        Product.objects.filter(pk=self.product.pk).update(stock_quantity=1)
        self.slot.capacity = 2
        self.slot.save(update_fields=["capacity"])
        data = combined_data(self.product, self.slot)
        first, second = self.race(lambda: self.place(data, uuid.uuid4()), lambda: self.place(data, uuid.uuid4()))
        self.assertEqual((first[0], second[0]), (201, 409))
        self.assertEqual(second[1]["error"]["code"], "CHECKOUT_CHANGED")
        self.assert_one_combined_submission()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)

    def test_standalone_booking_winning_slot_rolls_back_combined_order_and_stock(self):
        def standalone():
            return APIClient().post("/api/v1/surveys/bookings/", booking_data(self.slot),
                                    format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        first, second = self.race(standalone, lambda: self.place(self.data, uuid.uuid4()))
        self.assertEqual((first[0], second[0]), (201, 409))
        self.assertEqual(second[1]["error"]["code"], "SURVEY_SLOT_UNAVAILABLE")
        self.assertEqual((Order.objects.count(), OrderItem.objects.count(), InventoryMovement.objects.count()), (0, 0, 0))
        self.assertEqual((SurveyBooking.objects.count(), AuditEvent.objects.count(), EmailOutbox.objects.count()), (1, 1, 1))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)
