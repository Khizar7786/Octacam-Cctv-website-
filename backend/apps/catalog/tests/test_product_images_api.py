import io
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Brand, Category, Product, ProductImage
from apps.catalog.api.serializers import PublicProductListSerializer
from apps.catalog.selectors import get_public_products


def image_upload(*, name="camera.png", image_format="PNG", content_type="image/png", size=(32, 24)):
    image = Image.new("RGB", size, color="blue")
    output = io.BytesIO()
    image.save(output, format=image_format)
    return SimpleUploadedFile(name, output.getvalue(), content_type=content_type)


def remove_test_media(path):
    root = (settings.BASE_DIR / "media" / "test-uploads").resolve()
    target = path.resolve()
    if target.parent != root:
        raise ValueError("Test media cleanup target must be a child of the test media directory")
    shutil.rmtree(target)


class ProductImageApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="image-staff@example.com", password="test-password", full_name="Staff", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            email="image-customer@example.com", password="test-password", full_name="Customer",
        )
        brand = Brand.objects.create(name="Example Brand", slug="example-brand")
        category = Category.objects.create(name="Cameras", slug="cameras")
        cls.product = Product.objects.create(
            brand=brand,
            category=category,
            sku="IMAGE-001",
            slug="image-product",
            name="Image Product",
            short_description="Accurate short description.",
            full_description="Accurate full description.",
            regular_price="100.00",
            is_published=True,
        )

    def setUp(self):
        self.media_directory = settings.BASE_DIR / "media" / "test-uploads" / uuid.uuid4().hex
        self.media_directory.mkdir(parents=True)
        self.addCleanup(remove_test_media, self.media_directory)
        override = override_settings(MEDIA_ROOT=self.media_directory)
        override.enable()
        self.addCleanup(override.disable)
        self.client = APIClient()
        self.create_url = f"/api/v1/staff/catalog/products/{self.product.pk}/images/"

    def authorize(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")

    def create_image(self, *, name="camera.png", sort_order=None):
        payload = {"image": image_upload(name=name), "alt_text": "Front view of test camera"}
        if sort_order is not None:
            payload["sort_order"] = sort_order
        return self.client.post(self.create_url, payload, format="multipart")

    def test_staff_uploads_safe_image_and_public_api_returns_ordered_metadata(self):
        self.authorize(self.staff)
        later = self.create_image(name="../../danger.py", sort_order=5)
        self.assertEqual(later.status_code, 201)
        first = self.create_image(name="camera-front.png", sort_order=1)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["width"], 32)
        self.assertEqual(first.data["height"], 24)
        self.assertEqual(first.data["alt_text"], "Front view of test camera")

        stored = ProductImage.objects.get(pk=later.data["id"])
        self.assertTrue(stored.image.name.startswith(f"products/{self.product.pk}/"))
        self.assertTrue(stored.image.name.endswith(".png"))
        self.assertNotIn("danger", stored.image.name)
        self.assertEqual(Path(stored.image.path).read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

        self.client.credentials()
        listing = self.client.get("/api/v1/catalog/products/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["results"][0]["primary_image"]["id"], first.data["id"])
        self.assertTrue(listing.data["results"][0]["primary_image"]["image_url"].startswith("/media/"))
        self.assertEqual(listing.data["results"][0]["secondary_image"]["id"], later.data["id"])
        prefetched = list(get_public_products())
        with self.assertNumQueries(0):
            previews = PublicProductListSerializer(prefetched, many=True).data
        self.assertEqual(previews[0]["secondary_image"]["id"], later.data["id"])
        detail = self.client.get("/api/v1/catalog/products/image-product/")
        self.assertEqual([image["sort_order"] for image in detail.data["images"]], [1, 5])
        self.assertEqual(detail.data["images"][0]["id"], first.data["id"])

    def test_only_staff_can_create_edit_and_delete_images(self):
        self.authorize(self.staff)
        image_id = self.create_image().data["id"]
        detail_url = f"/api/v1/staff/catalog/product-images/{image_id}/"
        self.client.credentials()
        for user, expected in ((None, 401), (self.customer, 403)):
            with self.subTest(user=user):
                self.client.credentials()
                if user is not None:
                    self.authorize(user)
                self.assertEqual(self.create_image().status_code, expected)
                self.assertEqual(self.client.patch(detail_url, {"alt_text": "Changed"}, format="json").status_code,
                                 expected)
                self.assertEqual(self.client.delete(detail_url).status_code, expected)
        self.assertEqual(ProductImage.objects.count(), 1)
        self.assertEqual(ProductImage.objects.get(pk=image_id).alt_text, "Front view of test camera")

    def test_rejects_unsafe_or_invalid_uploads_without_writing_files(self):
        self.authorize(self.staff)
        invalid_uploads = (
            SimpleUploadedFile("script.jpg", b"print('not an image')", content_type="image/jpeg"),
            image_upload(name="wrong.jpg", content_type="image/jpeg"),
            image_upload(name="too-wide.png", size=(6001, 1)),
            SimpleUploadedFile("huge.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png"),
            image_upload(name="animation.gif", image_format="GIF", content_type="image/gif"),
        )
        for upload in invalid_uploads:
            with self.subTest(name=upload.name):
                response = self.client.post(
                    self.create_url, {"image": upload, "alt_text": "Test image"}, format="multipart",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("image", response.data["error"]["fields"])
        self.assertEqual(ProductImage.objects.count(), 0)
        self.assertEqual(list(self.media_directory.rglob("*")), [])

    def test_uploaded_metadata_is_removed_from_stored_image(self):
        output = io.BytesIO()
        metadata = PngInfo()
        metadata.add_text("Comment", "unsafe-user-supplied-marker")
        Image.new("RGB", (16, 16)).save(output, format="PNG", pnginfo=metadata)
        upload = SimpleUploadedFile("camera.png", output.getvalue(), content_type="image/png")
        self.authorize(self.staff)
        response = self.client.post(
            self.create_url, {"image": upload, "alt_text": "Camera front"}, format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        stored = ProductImage.objects.get(pk=response.data["id"])
        self.assertNotIn(b"unsafe-user-supplied-marker", Path(stored.image.path).read_bytes())

    def test_reorder_swaps_positions_and_rejects_duplicate_upload_order(self):
        self.authorize(self.staff)
        first_id = self.create_image(sort_order=0).data["id"]
        second_id = self.create_image(sort_order=1).data["id"]
        duplicate = self.create_image(sort_order=1)
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("sort_order", duplicate.data["error"]["fields"])
        self.assertEqual(ProductImage.objects.count(), 2)

        moved = self.client.patch(
            f"/api/v1/staff/catalog/product-images/{second_id}/",
            {"sort_order": 0, "alt_text": "New primary image"},
            format="json",
        )
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(ProductImage.objects.get(pk=first_id).sort_order, 1)
        self.assertEqual(ProductImage.objects.get(pk=second_id).sort_order, 0)
        self.client.credentials()
        listing = self.client.get("/api/v1/catalog/products/")
        self.assertEqual(listing.data["results"][0]["primary_image"]["id"], second_id)
        self.assertEqual(listing.data["results"][0]["secondary_image"]["id"], first_id)

    def test_replacement_and_delete_remove_old_files_after_commit(self):
        self.authorize(self.staff)
        image_id = self.create_image().data["id"]
        image = ProductImage.objects.get(pk=image_id)
        first_key = image.image.name
        detail_url = f"/api/v1/staff/catalog/product-images/{image_id}/"

        with self.captureOnCommitCallbacks(execute=True):
            replaced = self.client.patch(
                detail_url,
                {"image": image_upload(name="replacement.jpg", image_format="JPEG", content_type="image/jpeg")},
                format="multipart",
            )
        self.assertEqual(replaced.status_code, 200)
        image.refresh_from_db()
        second_key = image.image.name
        self.assertNotEqual(first_key, second_key)
        self.assertFalse(image.image.storage.exists(first_key))
        self.assertTrue(image.image.storage.exists(second_key))

        with self.captureOnCommitCallbacks(execute=True):
            deleted = self.client.delete(detail_url)
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(ProductImage.objects.filter(pk=image_id).exists())
        self.assertFalse(image.image.storage.exists(second_key))
        self.client.credentials()
        self.assertIsNone(self.client.get("/api/v1/catalog/products/").data["results"][0]["primary_image"])
        self.assertIsNone(self.client.get("/api/v1/catalog/products/").data["results"][0]["secondary_image"])

    def test_secondary_preview_is_null_without_two_images(self):
        self.assertIsNone(self.client.get("/api/v1/catalog/products/").data["results"][0]["secondary_image"])
        self.authorize(self.staff)
        image_id = self.create_image().data["id"]
        self.client.credentials()
        product = self.client.get("/api/v1/catalog/products/").data["results"][0]
        self.assertEqual(product["primary_image"]["id"], image_id)
        self.assertIsNone(product["secondary_image"])
