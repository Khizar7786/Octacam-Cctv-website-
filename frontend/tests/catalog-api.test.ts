import assert from "node:assert/strict";
import { test } from "node:test";
import { getPublicProductPage, getPublicProducts } from "../app/features/catalog/api.ts";
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
