import assert from "node:assert/strict";
import { test } from "node:test";
import { getAllPublicBrands, getPublicTaxonomy } from "../app/features/catalog/taxonomy.ts";
import { ApiError, createApiClient } from "../app/lib/api/client.ts";

const brand = (id: number) => ({ id, name: `Brand ${id}`, slug: `brand-${id}`, description: "", is_active: true, sort_order: id, created_at: "", updated_at: "" });

test("uploaded brand logo URLs are preserved and missing logos remain optional", async () => {
  for (const logo of [{ logo_url: "/media/brands/approved.webp" }, { logo_url: null }, {}]) {
    const client = createApiClient({ fetch: async () => Response.json({ ...brand(1), ...logo }) });
    const result = await getPublicTaxonomy(client, "brands", "brand-1");
    assert.equal(result.logo_url, "logo_url" in logo ? logo.logo_url : null);
  }
  const malformed = createApiClient({ fetch: async () => Response.json({ ...brand(1), logo_url: 12 }) });
  await assert.rejects(getPublicTaxonomy(malformed, "brands", "brand-1"), (error: unknown) => error instanceof ApiError && error.code === "UNEXPECTED_API_RESPONSE");
});

test("navigation collects every brand page in backend order", async () => {
  const requests: string[] = [];
  const client = createApiClient({ fetch: async (input) => {
    requests.push(String(input));
    const second = String(input).includes("page=2");
    return Response.json({ count: 21, next: second ? null : "http://internal:8000/api/v1/catalog/brands/?page=2", previous: null, results: second ? [brand(21)] : Array.from({ length: 20 }, (_, index) => brand(index + 1)) });
  } });
  const brands = await getAllPublicBrands(client);
  assert.deepEqual(brands.map(({ id }) => id), Array.from({ length: 21 }, (_, index) => index + 1));
  assert.deepEqual(requests, ["/api/v1/catalog/brands/", "/api/v1/catalog/brands/?page=2"]);
});

test("invalid and cyclic brand pagination fails instead of hanging navigation", async () => {
  for (const next of ["?page=1", "?page=invalid", "?page=9007199254740992"]) {
    const client = createApiClient({ fetch: async () => Response.json({ count: 2, next: `/api/v1/catalog/brands/${next}`, previous: null, results: [brand(1)] }) });
    await assert.rejects(getAllPublicBrands(client), (error: unknown) => error instanceof ApiError && error.code === "UNEXPECTED_API_RESPONSE");
  }
});
