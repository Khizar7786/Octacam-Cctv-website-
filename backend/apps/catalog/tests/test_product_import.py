import copy
import io
import json
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from PIL import Image
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditEvent
from apps.catalog.models import (
    Brand, Category, InventoryMovement, Product, ProductImage, ProductSpecificationValue,
    SpecificationChoice, SpecificationDefinition,
)
from apps.catalog.product_import_services import import_reviewed_products
from apps.catalog.services import create_product_draft


def reviewed_row(**changes):
    row = {
        "source_url": "https://smartlinks.pk/product/test-import-camera/",
        "brand": "test-brand", "category": "test-cameras",
        "sku": "IMPORT-001", "slug": "import-camera", "name": "Import Test Camera",
        "short_description": "Approved source summary.", "full_description": "Approved source description.",
        "regular_price": "1500.00", "sale_price": "1400.00", "currency": "PKR",
        "reviewed": True, "pricing_approved": True, "stock_quantity": 0, "is_published": False,
        "warranty_text": None, "specifications": [], "images": [],
    }
    row.update(changes)
    return row


def reviewed_batch(*rows):
    return {"schema_version": 1, "extracted_at": "2026-10-12T00:00:00+00:00", "products": list(rows)}


def remove_test_directory(path, parent):
    target = path.resolve()
    if target.parent != parent.resolve():
        raise ValueError("Test cleanup must stay in its own generated directory")
    shutil.rmtree(target)


class ProductImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="import-staff@example.com", password="test-password", full_name="Import Staff", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="import-customer@example.com", password="test-password", full_name="Customer",
        )
        cls.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        cls.category = Category.objects.create(name="Test Cameras", slug="test-cameras")

    def setUp(self):
        temporary_parent = settings.BASE_DIR / ".tmp"
        temporary_parent.mkdir(exist_ok=True)
        self.sources = temporary_parent / f"product-import-{uuid.uuid4().hex}"
        self.sources.mkdir()
        self.addCleanup(remove_test_directory, self.sources, temporary_parent)
        media_parent = settings.BASE_DIR / "media" / "test-uploads"
        media_parent.mkdir(parents=True, exist_ok=True)
        self.media = media_parent / uuid.uuid4().hex
        self.media.mkdir()
        self.addCleanup(remove_test_directory, self.media, media_parent)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        logging = patch("apps.catalog.product_import_services.logger.error")
        self.error_log = logging.start()
        self.addCleanup(logging.stop)

    def run_import(self, *rows, **options):
        return import_reviewed_products(batch=reviewed_batch(*rows), actor=self.staff, **options)

    def local_image(self, name="camera.png"):
        Image.new("RGB", (32, 24), color="blue").save(self.sources / name, format="PNG")
        return {"local_path": name, "alt_text": "Front view of the approved test camera"}

    def test_imports_draft_using_existing_taxonomies_and_records_approval(self):
        row = reviewed_row(sku=" import-001 ")
        original = copy.deepcopy(row)
        report = self.run_import(row, metadata={"input_sha256": "review-file-digest"})
        self.assertEqual(report["counts"]["created"], 1)
        product = Product.objects.get()
        self.assertEqual(product.sku, "IMPORT-001")
        self.assertEqual(product.regular_price, Decimal("1500.00"))
        self.assertEqual(product.sale_price, Decimal("1400.00"))
        self.assertFalse(product.is_published)
        self.assertEqual(product.stock_quantity, 0)
        self.assertEqual(product.warranty_text, "")
        self.assertEqual(Brand.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 0)
        audit = AuditEvent.objects.get(action="PRODUCT_IMPORTED")
        self.assertEqual(audit.actor, self.staff)
        self.assertTrue(audit.metadata["pricing_approved"])
        self.assertEqual(audit.metadata["input_sha256"], "review-file-digest")
        self.assertEqual(audit.metadata["source_url"], row["source_url"])
        self.assertEqual(row, original)

    def test_unreviewed_unapproved_or_non_boolean_approvals_are_rejected(self):
        for changes in ({"reviewed": False}, {"pricing_approved": False}, {"reviewed": "true"}, {"pricing_approved": 1}):
            with self.subTest(changes=changes):
                report = self.run_import(reviewed_row(**changes))
                self.assertEqual(report["counts"]["error"], 1)
                self.assertEqual(Product.objects.count(), 0)
                self.assertEqual(AuditEvent.objects.count(), 0)
        self.assertTrue(self.error_log.called)

    def test_stock_publication_and_currency_cannot_be_changed_by_import(self):
        for changes in ({"stock_quantity": 10}, {"stock_quantity": False}, {"is_published": True}, {"currency": "USD"}):
            with self.subTest(changes=changes):
                report = self.run_import(reviewed_row(**changes))
                self.assertEqual(report["counts"]["error"], 1)
        self.assertFalse(Product.objects.exists())

    def test_staff_permission_is_required_even_for_a_dry_run(self):
        inactive = copy.copy(self.staff)
        inactive.is_active = False
        for actor in (None, AnonymousUser(), self.customer, inactive):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                import_reviewed_products(batch=reviewed_batch(reviewed_row()), actor=actor, dry_run=True)
        self.assertFalse(Product.objects.exists())

    def test_missing_invalid_or_unapproved_prices_never_default_to_zero(self):
        for price in (None, "", "NaN", "-1.00", "1.001", "10000000000.00", 1500.0):
            with self.subTest(price=price):
                report = self.run_import(reviewed_row(regular_price=price))
                self.assertEqual(report["counts"]["error"], 1)
        for sale in ("1500.00", "1600.00", "-1.00"):
            self.assertEqual(self.run_import(reviewed_row(sale_price=sale))["counts"]["error"], 1)
        self.assertFalse(Product.objects.exists())

    def test_required_text_lengths_and_slug_conflicts_use_model_validation(self):
        for changes in ({"name": ""}, {"slug": None}, {"slug": "not a slug"}, {"short_description": "x" * 501}):
            self.assertEqual(self.run_import(reviewed_row(**changes))["counts"]["error"], 1)
        self.run_import(reviewed_row())
        result = self.run_import(reviewed_row(sku="SECOND-SKU"))
        self.assertEqual(result["counts"]["error"], 1)
        self.assertEqual(Product.objects.count(), 1)

    def test_reruns_and_duplicate_rows_skip_sku_without_modifying_existing_product(self):
        self.run_import(reviewed_row())
        product = Product.objects.get()
        product.stock_quantity = 7
        product.is_published = True
        product.save()
        report = self.run_import(
            reviewed_row(sku=" import-001 ", regular_price="999.00", sale_price=None),
            reviewed_row(sku="IMPORT-001", name="Changed name"),
        )
        self.assertEqual(report["counts"]["skipped"], 2)
        product.refresh_from_db()
        self.assertEqual(product.name, "Import Test Camera")
        self.assertEqual(product.regular_price, Decimal("1500.00"))
        self.assertEqual(product.stock_quantity, 7)
        self.assertTrue(product.is_published)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_duplicate_skus_within_batch_are_created_only_once(self):
        report = self.run_import(reviewed_row(), reviewed_row(sku="import-001", slug="other-slug"))
        self.assertEqual(report["counts"]["created"], 1)
        self.assertEqual(report["counts"]["skipped"], 1)
        self.assertEqual(Product.objects.count(), 1)

    def test_creates_only_explicitly_approved_missing_taxonomies(self):
        missing = reviewed_row(brand="Missing Brand")
        self.assertEqual(self.run_import(missing)["counts"]["error"], 1)
        row = reviewed_row(
            brand={"name": "New Brand", "slug": "new-brand", "create": True},
            category={"name": "New Cameras", "slug": "new-cameras", "create": True},
        )
        self.assertEqual(self.run_import(row)["counts"]["created"], 1)
        product = Product.objects.get()
        self.assertEqual(product.brand.slug, "new-brand")
        self.assertEqual(product.category.slug, "new-cameras")

    def test_conflicting_ambiguous_or_inactive_taxonomy_references_are_errors(self):
        rows = [reviewed_row(brand={"name": "Different Brand", "slug": "test-brand", "create": True})]
        Brand.objects.create(name="TEST BRAND", slug="second-test-brand")
        rows.append(reviewed_row(brand="Test Brand"))
        self.category.is_active = False
        self.category.save()
        rows.append(reviewed_row())
        for row in rows:
            self.assertEqual(self.run_import(row)["counts"]["error"], 1)
        self.assertEqual(Product.objects.count(), 0)

    def test_reuses_all_typed_specification_definitions_and_existing_choice(self):
        entries = []
        for key, kind, value, unit in (
            ("resolution", "choice", "5MP", ""), ("lens", "decimal", "3.6", "mm"),
            ("audio", "boolean", True, ""), ("channels", "integer", 4, ""), ("environment", "text", "Indoor", ""),
        ):
            definition = SpecificationDefinition.objects.create(
                category=self.category, key=key, label=key.title(), data_type=kind, unit=unit,
            )
            if kind == "choice":
                SpecificationChoice.objects.create(definition=definition, value="5mp", label="5 MP")
            entries.append({"key": key, "value": value})
        report = self.run_import(reviewed_row(specifications=entries))
        self.assertEqual(report["counts"]["created"], 1)
        self.assertEqual(ProductSpecificationValue.objects.count(), 5)
        self.assertEqual(SpecificationDefinition.objects.count(), 5)
        self.assertEqual(SpecificationChoice.objects.count(), 1)
        self.assertEqual(ProductSpecificationValue.objects.get(definition__key="lens").decimal_value, Decimal("3.6"))

    def test_new_definitions_and_choices_require_explicit_review_mapping(self):
        entries = [{
            "key": "resolution", "label": "Resolution", "data_type": "choice", "create": True,
            "value": "5mp", "create_choice": True, "choice_label": "5 MP",
        }]
        report = self.run_import(reviewed_row(specifications=entries))
        self.assertEqual(report["counts"]["created"], 1)
        self.assertEqual(SpecificationDefinition.objects.count(), 1)
        self.assertEqual(SpecificationChoice.objects.count(), 1)
        self.assertFalse(SpecificationDefinition.objects.get().is_required)

    def test_raw_labels_conflicting_types_missing_choices_and_bad_values_are_errors(self):
        definition = SpecificationDefinition.objects.create(
            category=self.category, key="channels", label="Channels", data_type="integer",
        )
        for entries in (
            [{"label": "Source label", "value": "Source value"}],
            [{"key": "missing", "value": "Source value"}],
            [{"key": "channels", "data_type": "text", "value": 4}],
            [{"key": "channels", "unit": "other", "value": 4}],
            [{"key": "channels", "value": "4"}],
            [{"key": "channels", "value": 4}, {"key": "channels", "value": 8}],
        ):
            self.assertEqual(self.run_import(reviewed_row(specifications=entries))["counts"]["error"], 1)
        definition.data_type = "choice"
        definition.save()
        self.assertEqual(self.run_import(reviewed_row(specifications=[{"key": "channels", "value": "4"}]))["counts"]["error"], 1)
        self.assertFalse(Product.objects.exists())

    def test_local_images_use_existing_service_and_reruns_do_not_duplicate_files(self):
        images = [self.local_image(), self.local_image("back.png")]
        row = reviewed_row(images=images)
        report = self.run_import(row, image_root=self.sources)
        self.assertEqual(report["counts"]["created"], 1)
        self.assertEqual(report["rows"][0]["image_count"], 2)
        self.assertEqual(list(ProductImage.objects.values_list("sort_order", flat=True)), [0, 1])
        self.assertTrue(all(image.image.name.startswith(f"products/{image.product_id}/") for image in ProductImage.objects.all()))
        self.assertEqual(self.run_import(row, image_root=self.sources)["counts"]["skipped"], 1)
        self.assertEqual(len(list(self.media.rglob("*.png"))), 2)

    def test_remote_images_are_not_fetched_and_are_reported_as_skipped(self):
        report = self.run_import(reviewed_row(images=[{"url": "https://example.com/photo.jpg", "local_path": None}]))
        self.assertEqual(report["rows"][0]["remote_images_skipped"], 1)
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_images_reject_missing_root_traversal_bad_files_and_blank_alt_text(self):
        image = self.local_image()
        self.assertEqual(self.run_import(reviewed_row(images=[image]))["counts"]["error"], 1)
        (self.sources / "bad.png").write_bytes(b"not an image")
        for entry in (
            {"local_path": "../outside.png", "alt_text": "Outside"},
            {"local_path": str((self.sources / "camera.png").resolve()), "alt_text": "Absolute"},
            {"local_path": "bad.png", "alt_text": "Bad file"},
            {"local_path": "missing.png", "alt_text": "Missing file"},
            {"local_path": "camera.png", "alt_text": ""},
        ):
            self.assertEqual(self.run_import(reviewed_row(images=[entry]), image_root=self.sources)["counts"]["error"], 1)
        self.assertFalse(Product.objects.exists())
        self.assertEqual(list(self.media.rglob("*")), [])

    def test_failed_product_rolls_back_new_taxonomies_specs_and_uploaded_files(self):
        row = reviewed_row(
            brand={"name": "Rollback Brand", "slug": "rollback-brand", "create": True},
            category={"name": "Rollback Cameras", "slug": "rollback-cameras", "create": True},
            specifications=[{"key": "notes", "label": "Notes", "data_type": "text", "create": True, "value": "Source value"}],
            images=[self.local_image()],
        )
        with patch("apps.catalog.product_import_services.record_audit_event", side_effect=RuntimeError("Audit failed")):
            self.assertEqual(self.run_import(row, image_root=self.sources)["counts"]["error"], 1)
        self.assertFalse(Product.objects.exists())
        self.assertEqual(Brand.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 1)
        self.assertFalse(SpecificationDefinition.objects.exists())
        self.assertFalse(ProductImage.objects.exists())
        self.assertFalse(any(path.is_file() for path in self.media.rglob("*")))
        self.assertTrue((self.sources / "camera.png").is_file())
        self.assertEqual(self.run_import(row, image_root=self.sources)["counts"]["created"], 1)

    def test_dry_run_validates_whole_batch_without_records_audits_or_storage_writes(self):
        row = reviewed_row(
            brand={"name": "Dry Brand", "slug": "dry-brand", "create": True},
            category={"name": "Dry Cameras", "slug": "dry-cameras", "create": True},
            specifications=[{"key": "notes", "label": "Notes", "data_type": "text", "create": True, "value": "Source value"}],
            images=[self.local_image()],
        )
        with patch("apps.catalog.product_import_services.create_product_image") as image_service:
            report = self.run_import(row, copy.deepcopy(row), dry_run=True, image_root=self.sources)
        self.assertEqual(report["counts"]["validated"], 1)
        self.assertEqual(report["counts"]["skipped"], 1)
        self.assertTrue(all(result["product_id"] is None for result in report["rows"]))
        image_service.assert_not_called()
        self.assertFalse(Product.objects.exists())
        self.assertFalse(SpecificationDefinition.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertEqual(Brand.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(list(self.media.rglob("*")), [])

    def test_one_invalid_row_does_not_undo_valid_rows(self):
        report = self.run_import(reviewed_row(), reviewed_row(sku="BAD-ROW", slug="bad-row", pricing_approved=False))
        self.assertEqual(report["counts"]["created"], 1)
        self.assertEqual(report["counts"]["error"], 1)
        self.assertEqual(Product.objects.count(), 1)

    def test_real_import_cannot_be_enclosed_in_a_later_rollback(self):
        with transaction.atomic():
            report = self.run_import(reviewed_row(images=[self.local_image()]), image_root=self.sources)
            self.assertEqual(report["counts"]["error"], 1)
        self.assertFalse(Product.objects.exists())
        self.assertEqual(list(self.media.rglob("*")), [])

    def test_command_dry_run_and_real_import_write_reports_and_preserve_input(self):
        input_path = self.sources / "reviewed.json"
        source = json.dumps(reviewed_batch(reviewed_row()))
        input_path.write_text(source, encoding="utf-8")
        dry_report = self.sources / "dry-report.json"
        call_command("import_products", str(input_path), actor=self.staff.email, dry_run=True,
                     report=dry_report, stdout=io.StringIO())
        self.assertEqual(json.loads(dry_report.read_text())["counts"]["validated"], 1)
        self.assertFalse(Product.objects.exists())
        report_path = self.sources / "report.json"
        call_command("import_products", str(input_path), actor=self.staff.email.upper(), report=report_path, stdout=io.StringIO())
        self.assertEqual(json.loads(report_path.read_text())["counts"]["created"], 1)
        self.assertEqual(input_path.read_text(), source)
        self.assertEqual(len(AuditEvent.objects.get().metadata["input_sha256"]), 64)

    def test_command_partial_failure_is_nonzero_and_report_retains_successes(self):
        input_path = self.sources / "reviewed.json"
        input_path.write_text(json.dumps(reviewed_batch(reviewed_row(), reviewed_row(sku="BAD", pricing_approved=False))))
        report_path = self.sources / "report.json"
        with self.assertRaisesMessage(CommandError, "Some rows failed"):
            call_command("import_products", str(input_path), actor=self.staff.email, report=report_path,
                         stdout=io.StringIO(), stderr=io.StringIO())
        report = json.loads(report_path.read_text())
        self.assertEqual(report["counts"]["created"], 1)
        self.assertEqual(report["counts"]["error"], 1)
        self.assertTrue(Product.objects.filter(sku="IMPORT-001").exists())

    def test_command_refuses_existing_reports_bad_json_and_nonstaff_actor(self):
        input_path = self.sources / "reviewed.json"
        input_path.write_text(json.dumps(reviewed_batch(reviewed_row())))
        with self.assertRaises(CommandError):
            call_command("import_products", str(input_path), actor=self.staff.email, report=input_path)
        with self.assertRaises(CommandError):
            call_command("import_products", str(input_path), actor=self.customer.email, report=self.sources / "denied.json")
        bad = self.sources / "invalid.json"
        bad.write_text("invalid")
        with self.assertRaises(CommandError):
            call_command("import_products", str(bad), actor=self.staff.email, report=self.sources / "bad-report.json")
        self.assertFalse(Product.objects.exists())

    def test_invalid_batch_version_is_rejected_before_writing_products(self):
        for batch in ({}, {"schema_version": True, "products": []}, {"schema_version": 2, "products": []}):
            with self.subTest(batch=batch), self.assertRaises(ValidationError):
                import_reviewed_products(batch=batch, actor=self.staff)


class ProductImportConcurrencyTests(TransactionTestCase):
    def test_concurrent_imports_of_same_sku_create_one_draft_and_one_audit(self):
        staff = get_user_model().objects.create_user(
            email="concurrent-import@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        Brand.objects.create(name="Test Brand", slug="test-brand")
        Category.objects.create(name="Test Cameras", slug="test-cameras")
        barrier = Barrier(2)

        def concurrent_create(*, data):
            barrier.wait(timeout=10)
            return create_product_draft(data=data)

        def run():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=staff.pk)
                return import_reviewed_products(batch=reviewed_batch(reviewed_row()), actor=actor)
            finally:
                close_old_connections()

        with patch("apps.catalog.product_import_services.create_product_draft", side_effect=concurrent_create):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(run), pool.submit(run)]
                reports = [future.result(timeout=20) for future in futures]
        self.assertEqual(sorted(report["rows"][0]["status"] for report in reports), ["created", "skipped"])
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="PRODUCT_IMPORTED").count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 0)
