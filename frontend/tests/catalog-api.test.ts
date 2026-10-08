import assert from "node:assert/strict";
import { test } from "node:test";
import { getPublicProductDetail, getPublicProductPage, getPublicProducts, hasValidSale } from "../app/features/catalog/api.ts";
import { clampQuantity, galleryImageIndex } from "../app/features/catalog/product.ts";
import { ApiError, apiPath, createApiClient } from "../app/lib/api/client.ts";

const product = {
  id: 7,
  brand: { id: 1, name: "Hikvision", slug: "hikvision" },
  category: { id: 2, name: "Cameras", slug: "cameras" },
  sku: "DS-2CE",
  slug: "ds-2ce",
  name: "Test camera",
  short_description: "Contract fixture",
  regular_price: "7999.00",
  sale_price: "7499.00",
  selling_price: "7499.00",
  stock_quantity: 3,
  is_in_stock: true,
  primary_image: null,
};

test("manual product gallery wraps in both directions and handles a single or missing image", () => {
  assert.equal(galleryImageIndex(2, 1, 3), 0);
  assert.equal(galleryImageIndex(0, -1, 3), 2);
  assert.equal(galleryImageIndex(1, 1, 3), 2);
  assert.equal(galleryImageIndex(0, 1, 1), 0);
  assert.equal(galleryImageIndex(0, -1, 0), 0);
});

test("preserves decimal strings and normalizes internal pagination links", async () => {
  const requestedUrls: string[] = [];
  const client = createApiClient({
    fetch: async (input) => {
      requestedUrls.push(String(input));
      return Response.json({
        count: 21,
        next: "http://backend-internal:8000/api/v1/catalog/products/?page=2",
        previous: null,
        results: [product],
      });
    },
  });

  const first = await getPublicProducts(client);
  assert.equal(first.results[0]?.regular_price, "7999.00");
  assert.equal(first.results[0]?.sale_price, "7499.00");
  assert.equal(typeof first.results[0]?.selling_price, "string");
  assert.equal(first.next, "/api/v1/catalog/products/?page=2");

  assert.ok(first.next);
  await getPublicProductPage(client, first.next);
  assert.deepEqual(requestedUrls, [
    "/api/v1/catalog/products/",
    "/api/v1/catalog/products/?page=2",
  ]);
});

test("supports URL search parameters without changing their decimal values", async () => {
  let requestedUrl = "";
  const client = createApiClient({
    fetch: async (input) => {
      requestedUrl = String(input);
      return Response.json({ count: 0, next: null, previous: null, results: [] });
    },
  });
  const searchParams = new URLSearchParams({ min_price: "7999.00", q: "DS-2CE" });

  await getPublicProducts(client, { searchParams });
  assert.equal(requestedUrl, "/api/v1/catalog/products/?min_price=7999.00&q=DS-2CE");
});

test("rejects malformed successful data as an unexpected API response", async () => {
  const malformed = { count: 1, next: null, previous: null, results: [{ ...product, selling_price: 7499 }] };
  const client = createApiClient({ fetch: async () => Response.json(malformed) });

  await assert.rejects(getPublicProducts(client), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.code, "UNEXPECTED_API_RESPONSE");
    assert.equal(error.status, 200);
    return true;
  });
});

test("rejects a product page that points pagination at another API collection", async () => {
  const client = createApiClient({
    fetch: async () => Response.json({
      count: 1,
      next: "http://backend-internal:8000/api/v1/catalog/brands/?page=2",
      previous: null,
      results: [product],
    }),
  });

  await assert.rejects(getPublicProducts(client), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.code, "UNEXPECTED_API_RESPONSE");
    return true;
  });
});

test("only follows product-list pagination paths", async () => {
  const client = createApiClient({ fetch: async () => Response.json({}) });
  await assert.rejects(
    getPublicProductPage(client, apiPath("/api/v1/catalog/brands/?page=2")),
    /must target the public product collection/,
  );
});

test("public detail preserves image, specification, warranty, money, and stock fields", async () => {
  const requested: string[] = [];
  const detail = {
    ...product, full_description: "Verified product description", warranty_text: "Supplier-provided warranty",
    images: [{ id: 4, image_url: "/media/products/camera.webp", alt_text: "Camera front",
      sort_order: 0, width: 640, height: 480, created_at: "2026-10-05T00:00:00Z" }],
    specifications: [
      { definition: 1, key: "resolution", label: "Resolution", data_type: "choice", unit: "", value: "4mp", display_value: "4 MP" },
      { definition: 2, key: "outdoor", label: "Outdoor use", data_type: "boolean", unit: "", value: false, display_value: "No" },
      { definition: 3, key: "capacity", label: "Capacity", data_type: "decimal", unit: "TB", value: "2.0000", display_value: "2.0000 TB" },
      { definition: 4, key: "channels", label: "Channels", data_type: "integer", unit: "", value: 8, display_value: "8" },
      { definition: 5, key: "interface", label: "Interface", data_type: "text", unit: "", value: "SATA", display_value: "SATA" },
    ],
    updated_at: "2026-10-05T00:00:00Z",
  };
  const client = createApiClient({ fetch: async (input) => { requested.push(String(input)); return Response.json(detail); } });
  const result = await getPublicProductDetail(client, "ds-2ce");
  assert.deepEqual(requested, ["/api/v1/catalog/products/ds-2ce/"]);
  assert.equal(result.selling_price, "7499.00");
  assert.equal(result.specifications[1]?.display_value, "No");
  assert.equal(result.specifications[2]?.value, "2.0000");
  assert.equal(result.specifications[3]?.display_value, "8");
  assert.equal(result.specifications[4]?.display_value, "SATA");
  assert.equal(result.images[0]?.alt_text, "Camera front");
  assert.equal(result.warranty_text, "Supplier-provided warranty");
  assert.equal(hasValidSale(result), true);
  assert.equal(hasValidSale({ ...result, sale_price: result.regular_price, selling_price: result.regular_price }), false);
});

test("detail rejects contradictory stock and never turns an unpublished 404 into a product", async () => {
  const inconsistent = { ...product, stock_quantity: 0, full_description: "", warranty_text: "", images: [], specifications: [], updated_at: "2026-10-05T00:00:00Z" };
  const client = createApiClient({ fetch: async () => Response.json(inconsistent) });
  await assert.rejects(getPublicProductDetail(client, "ds-2ce"), (error: unknown) => error instanceof ApiError && error.code === "UNEXPECTED_API_RESPONSE");
  const missing = createApiClient({ fetch: async () => Response.json({ error: { code: "NOT_FOUND", message: "Not found.", fields: {} } }, { status: 404 }) });
  await assert.rejects(getPublicProductDetail(missing, "unpublished"), (error: unknown) => error instanceof ApiError && error.status === 404);
});

test("requested quantity stays within the stock currently known from Django", () => {
  assert.equal(clampQuantity("4", 3), 3);
  assert.equal(clampQuantity("0", 3), 1);
  assert.equal(clampQuantity("2.5", 3), 1);
  assert.equal(clampQuantity("2", 3), 2);
  assert.equal(clampQuantity("9", 0), 0);
});

test("list previews preserve image metadata and tolerate older API responses", async () => {
  const secondary_image = { id: 9, image_url: "/media/products/back.webp", alt_text: "Rear view", sort_order: 5, width: 640, height: 480, created_at: "2026-10-08T00:00:00Z" };
  for (const item of [product, { ...product, secondary_image: null }, { ...product, secondary_image }]) {
    const client = createApiClient({ fetch: async () => Response.json({ count: 1, next: null, previous: null, results: [item] }) });
    const page = await getPublicProducts(client);
    assert.deepEqual(page.results[0].secondary_image, "secondary_image" in item ? item.secondary_image : null);
  }
  const invalid = createApiClient({ fetch: async () => Response.json({ count: 1, next: null, previous: null, results: [{ ...product, secondary_image: { ...secondary_image, width: 0 } }] }) });
  await assert.rejects(getPublicProducts(invalid), (error: unknown) => error instanceof ApiError && error.code === "UNEXPECTED_API_RESPONSE");
});
