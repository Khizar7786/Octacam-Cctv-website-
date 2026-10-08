import io
import uuid

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.brand_services import save_brand
from apps.catalog.models import Brand
from apps.catalog.tests.test_product_images_api import image_upload, remove_test_media


class LogoObjectStorage(Storage):
    """A storage URL and file operations must work without a local path."""

    def __init__(self):
        self.files = {}

    def _open(self, name, mode="rb"):
        return ContentFile(self.files[name], name=name)

    def _save(self, name, content):
        self.files[name] = content.read()
        return name

    def exists(self, name):
        return name in self.files

    def delete(self, name):
        self.files.pop(name, None)

    def url(self, name):
        return f"https://media.example.test/{name}"


class BrandLogoApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="logo-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="logo-customer@example.com", password="test-password", full_name="Customer",
        )
        cls.brand = Brand.objects.create(name="Logo Brand", slug="logo-brand")

    def setUp(self):
        self.media_directory = settings.BASE_DIR / "media" / "test-uploads" / uuid.uuid4().hex
        self.media_directory.mkdir(parents=True)
        self.addCleanup(remove_test_media, self.media_directory)
        override = override_settings(MEDIA_ROOT=self.media_directory)
        override.enable()
        self.addCleanup(override.disable)
        self.client = APIClient()
        self.collection = "/api/v1/staff/catalog/brands/"
        self.detail = f"{self.collection}{self.brand.pk}/"
        self.authorize(self.staff)

    def authorize(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")

    def upload_logo(self, upload=None):
        return self.client.patch(
            self.detail, {"logo": upload or image_upload(name="logo.png")}, format="multipart",
        )

    def test_json_without_a_logo_is_backward_compatible_and_responses_are_nullable(self):
        created = self.client.post(self.collection, {"name": "Plain", "slug": "plain"}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertIsNone(created.data["logo_url"])
        self.assertNotIn("logo", created.data)
        self.assertNotIn("remove_logo", created.data)
        self.assertIsNone(self.client.get("/api/v1/catalog/brands/plain/").data["logo_url"])
        for route in (self.collection, "/api/v1/catalog/brands/"):
            self.assertTrue(all(row["logo_url"] is None for row in self.client.get(route).data["results"]))

    def test_staff_create_with_png_jpeg_and_webp_and_public_responses_use_storage_url(self):
        for image_format, mime, extension in (("PNG", "image/png", "png"),
                                              ("JPEG", "image/jpeg", "jpg"),
                                              ("WEBP", "image/webp", "webp")):
            with self.subTest(image_format=image_format):
                slug = f"brand-{extension}"
                created = self.client.post(self.collection, {
                    "name": f"Brand {extension}", "slug": slug,
                    "logo": image_upload(name="untrusted-name.py", image_format=image_format, content_type=mime),
                }, format="multipart")
                self.assertEqual(created.status_code, 201)
                self.assertTrue(created.data["is_active"])
                brand = Brand.objects.get(pk=created.data["id"])
                self.assertTrue(brand.logo.name.startswith("brands/"))
                self.assertTrue(brand.logo.name.endswith(f".{extension}"))
                self.assertNotIn("untrusted-name", brand.logo.name)
                self.assertTrue(brand.logo.storage.exists(brand.logo.name))
                self.assertEqual(created.data["logo_url"], brand.logo.url)
                self.assertEqual(self.client.get(f"/api/v1/catalog/brands/{slug}/").data["logo_url"], brand.logo.url)
                for route in (self.collection, "/api/v1/catalog/brands/"):
                    row = next(row for row in self.client.get(route).data["results"] if row["id"] == brand.pk)
                    self.assertEqual(row["logo_url"], brand.logo.url)

    def test_replacement_defers_old_file_deletion_until_commit_and_json_edits_preserve_logo(self):
        self.assertEqual(self.upload_logo().status_code, 200)
        self.brand.refresh_from_db()
        old_key = self.brand.logo.name
        storage = self.brand.logo.storage
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.upload_logo(image_upload(image_format="WEBP", content_type="image/webp"))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(storage.exists(old_key))
        self.assertEqual(len(callbacks), 1)
        self.brand.refresh_from_db()
        new_key = self.brand.logo.name
        self.assertNotEqual(old_key, new_key)
        self.assertFalse(storage.exists(old_key))
        self.assertTrue(storage.exists(new_key))
        edited = self.client.patch(self.detail, {"description": "Updated", "remove_logo": False}, format="json")
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.data["logo_url"], self.brand.logo.url)
        self.brand.refresh_from_db()
        self.assertEqual(self.brand.logo.name, new_key)

    def test_removal_supports_json_null_and_multipart_or_json_flag_and_is_repeatable(self):
        for payload, request_format in (({"logo": None}, "json"),
                                        ({"remove_logo": "true"}, "multipart"),
                                        ({"remove_logo": True}, "json")):
            with self.subTest(request_format=request_format, payload=payload):
                self.assertEqual(self.upload_logo().status_code, 200)
                self.brand.refresh_from_db()
                old_key = self.brand.logo.name
                storage = self.brand.logo.storage
                with self.captureOnCommitCallbacks(execute=True):
                    removed = self.client.patch(self.detail, payload, format=request_format)
                    self.assertTrue(storage.exists(old_key))
                self.assertEqual(removed.status_code, 200)
                self.assertIsNone(removed.data["logo_url"])
                self.brand.refresh_from_db()
                self.assertFalse(self.brand.logo)
                self.assertFalse(storage.exists(old_key))
                self.assertEqual(self.client.patch(self.detail, payload, format=request_format).status_code, 200)
                self.assertIsNone(self.client.get("/api/v1/catalog/brands/logo-brand/").data["logo_url"])

    def test_rejects_invalid_oversized_mismatched_and_unsupported_uploads_without_files(self):
        invalid_uploads = (
            SimpleUploadedFile("invalid.png", b"not an image", content_type="image/png"),
            SimpleUploadedFile("empty.png", b"", content_type="image/png"),
            image_upload(name="mismatch.jpg", content_type="image/jpeg"),
            image_upload(name="unsupported.gif", image_format="GIF", content_type="image/gif"),
            image_upload(name="too-wide.png", size=(6001, 1)),
            SimpleUploadedFile("oversized.png", b"x" * (2 * 1024 * 1024 + 1), content_type="image/png"),
        )
        for upload in invalid_uploads:
            with self.subTest(name=upload.name):
                response = self.client.post(self.collection, {
                    "name": "Invalid", "slug": "invalid", "logo": upload,
                }, format="multipart")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
                self.assertIn("logo", response.data["error"]["fields"])
        self.assertEqual(Brand.objects.count(), 1)
        self.assertEqual(list(self.media_directory.rglob("*")), [])

    def test_accepts_exactly_two_mb_and_rejects_one_byte_more(self):
        content = image_upload().read()
        content += b"\0" * (settings.BRAND_LOGO_MAX_BYTES - len(content))
        self.assertEqual(self.upload_logo(SimpleUploadedFile("limit.png", content, "image/png")).status_code, 200)
        self.brand.refresh_from_db()
        old_key = self.brand.logo.name
        response = self.upload_logo(SimpleUploadedFile("over-limit.png", content + b"\0", "image/png"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("2 MB", response.data["error"]["fields"]["logo"][0])
        self.brand.refresh_from_db()
        self.assertEqual(self.brand.logo.name, old_key)

    def test_failed_replacement_preserves_existing_logo_and_other_fields(self):
        self.upload_logo()
        self.brand.refresh_from_db()
        old_key = self.brand.logo.name
        response = self.client.patch(self.detail, {
            "description": "Must not persist", "logo": SimpleUploadedFile("bad.png", b"bad", "image/png"),
        }, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.brand.refresh_from_db()
        self.assertEqual(self.brand.logo.name, old_key)
        self.assertEqual(self.brand.description, "")
        self.assertTrue(self.brand.logo.storage.exists(old_key))
        self.assertEqual(len([path for path in self.media_directory.rglob("*") if path.is_file()]), 1)

    def test_upload_and_remove_conflict_and_json_storage_paths_are_rejected(self):
        response = self.client.patch(self.detail, {
            "logo": image_upload(), "remove_logo": "true",
        }, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("logo", response.data["error"]["fields"])
        response = self.client.patch(self.detail, {"logo": "brands/arbitrary.png"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.media_directory.rglob("*")), [])

    def test_only_current_active_staff_can_upload_replace_and_remove(self):
        self.upload_logo()
        self.brand.refresh_from_db()
        old_key = self.brand.logo.name
        for user, expected in ((None, 401), (self.customer, 403)):
            with self.subTest(expected=expected):
                self.client.credentials()
                if user:
                    self.authorize(user)
                created = self.client.post(self.collection, {
                    "name": "Denied", "slug": "denied", "logo": image_upload(),
                }, format="multipart")
                self.assertEqual(created.status_code, expected)
                self.assertEqual(self.upload_logo().status_code, expected)
                self.assertEqual(self.client.patch(self.detail, {"remove_logo": "true"}, format="multipart").status_code,
                                 expected)
                self.assertEqual(self.client.patch(self.detail, {"logo": None}, format="json").status_code, expected)
        self.authorize(self.staff)
        get_user_model().objects.filter(pk=self.staff.pk).update(is_staff=False)
        self.assertEqual(self.upload_logo().status_code, 403)
        get_user_model().objects.filter(pk=self.staff.pk).update(is_staff=True, is_active=False)
        self.assertEqual(self.upload_logo().status_code, 401)
        self.brand.refresh_from_db()
        self.assertEqual(self.brand.logo.name, old_key)
        self.assertEqual(Brand.objects.count(), 1)
        self.assertEqual(len([path for path in self.media_directory.rglob("*") if path.is_file()]), 1)

    def test_database_failure_cleans_new_file_and_preserves_old_file(self):
        self.upload_logo()
        self.brand.refresh_from_db()
        old_key = self.brand.logo.name
        Brand.objects.create(name="Occupied", slug="occupied")
        with self.assertRaises(ValidationError):
            save_brand(instance=self.brand, data={"name": "Occupied", "logo": image_upload()})
        self.brand.refresh_from_db()
        self.assertEqual(self.brand.name, "Logo Brand")
        self.assertEqual(self.brand.logo.name, old_key)
        self.assertTrue(self.brand.logo.storage.exists(old_key))
        self.assertEqual(len([path for path in self.media_directory.rglob("*") if path.is_file()]), 1)

    def test_enclosing_transaction_rollback_preserves_old_file_and_reference(self):
        self.upload_logo()
        self.brand.refresh_from_db()
        old_key = self.brand.logo.name
        for data in ({"remove_logo": True}, {"logo": image_upload()}):
            with self.subTest(removal="remove_logo" in data):
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    with transaction.atomic():
                        save_brand(instance=self.brand, data=data)
                        transaction.set_rollback(True)
                self.assertEqual(callbacks, [])
                self.brand.refresh_from_db()
                self.assertEqual(self.brand.logo.name, old_key)
                self.assertTrue(self.brand.logo.storage.exists(old_key))

    def test_stale_instance_replacement_locks_and_cleans_the_current_logo(self):
        first_instance = Brand.objects.get(pk=self.brand.pk)
        stale_instance = Brand.objects.get(pk=self.brand.pk)
        first = save_brand(instance=first_instance, data={"logo": image_upload()})
        first_key = first.logo.name
        with self.captureOnCommitCallbacks(execute=True):
            second = save_brand(instance=stale_instance, data={"logo": image_upload()})
        self.assertFalse(second.logo.storage.exists(first_key))
        self.assertTrue(second.logo.storage.exists(second.logo.name))

    def test_normalization_removes_metadata_and_preserves_png_transparency(self):
        output = io.BytesIO()
        metadata = PngInfo()
        metadata.add_text("Comment", "private-image-metadata")
        Image.new("RGBA", (16, 16), color=(10, 20, 30, 0)).save(output, format="PNG", pnginfo=metadata)
        response = self.upload_logo(SimpleUploadedFile("transparent.png", output.getvalue(), "image/png"))
        self.assertEqual(response.status_code, 200)
        self.brand.refresh_from_db()
        with self.brand.logo.open("rb") as stored:
            content = stored.read()
        self.assertNotIn(b"private-image-metadata", content)
        with Image.open(io.BytesIO(content)) as decoded:
            self.assertEqual(decoded.mode, "RGBA")
            self.assertEqual(decoded.getpixel((0, 0))[3], 0)

    @override_settings(STORAGES={
        "default": {"BACKEND": "apps.catalog.tests.test_brand_logos_api.LogoObjectStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_object_storage_urls_and_cleanup_do_not_require_local_paths(self):
        uploaded = self.upload_logo()
        self.assertEqual(uploaded.status_code, 200)
        self.brand.refresh_from_db()
        old_key = self.brand.logo.name
        self.assertEqual(uploaded.data["logo_url"], f"https://media.example.test/{old_key}")
        with self.captureOnCommitCallbacks(execute=True):
            replaced = self.upload_logo()
        self.assertEqual(replaced.status_code, 200)
        self.assertFalse(self.brand.logo.storage.exists(old_key))
        with self.captureOnCommitCallbacks(execute=True):
            removed = self.client.patch(self.detail, {"logo": None}, format="json")
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(removed.data["logo_url"])

    def test_local_media_can_serve_the_uploaded_logo_in_development(self):
        self.upload_logo()
        self.brand.refresh_from_db()

        class MediaUrls:
            urlpatterns = []

        with override_settings(DEBUG=True, ROOT_URLCONF=MediaUrls):
            MediaUrls.urlpatterns = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
            response = self.client.get(self.brand.logo.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")
            content = b"".join(response.streaming_content)
            self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_inactive_brands_still_hide_their_public_logo(self):
        self.upload_logo()
        self.client.patch(self.detail, {"is_active": False}, format="json")
        self.assertEqual(self.client.get("/api/v1/catalog/brands/logo-brand/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/catalog/brands/").data["count"], 0)
        self.assertIsNotNone(self.client.get(self.collection).data["results"][0]["logo_url"])
