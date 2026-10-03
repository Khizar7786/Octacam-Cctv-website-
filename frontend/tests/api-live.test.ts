import assert from "node:assert/strict";
import { test } from "node:test";
import { getPublicProducts } from "../app/features/catalog/api.ts";
import { browserApiClient } from "../app/lib/api/browser-client.ts";
import { ApiError, createApiClient } from "../app/lib/api/client.ts";

const frontendOrigin = process.env.OCTACAM_FRONTEND_ORIGIN ?? "http://127.0.0.1:5173";

test("the development proxy serves the real public catalog to a browser client", async () => {
  const nativeFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    if (typeof input !== "string") throw new TypeError("The browser client must send a relative string path.");
    assert.match(input, /^\/api\/v1\//);
    return nativeFetch(new URL(input, frontendOrigin), init);
  };

  let products;
  try {
    products = await getPublicProducts(browserApiClient, { signal: AbortSignal.timeout(5_000) });
  } finally {
    globalThis.fetch = nativeFetch;
  }

  assert.ok(Number.isInteger(products.count));
  assert.ok(Array.isArray(products.results));
});

test("a direct foundation request server-renders the real catalog result", async () => {
  const productsResponse = await fetch(`${frontendOrigin}/api/v1/catalog/products/`, {
    signal: AbortSignal.timeout(5_000),
  });
  const products = await productsResponse.json() as { count: number };
  const response = await fetch(`${frontendOrigin}/foundation`, { signal: AbortSignal.timeout(5_000) });
  const html = await response.text();

  assert.equal(response.status, 200);
  assert.match(html, /public catalog was loaded by the server API client during SSR/i);
  if (products.count === 0) {
    assert.match(html, /live catalog currently has no published products/i);
  } else {
    assert.match(html, new RegExp(`${products.count} published products are available`, "i"));
  }
});

test("the development proxy preserves Django's structured validation error", async () => {
  const client = createApiClient({
    fetch: async (input, init) => fetch(new URL(String(input), frontendOrigin), init),
  });

  await assert.rejects(
    getPublicProducts(client, { searchParams: new URLSearchParams({ min_price: "not-money" }) }),
    (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 400);
      assert.equal(error.code, "VALIDATION_ERROR");
      assert.ok(error.fields.min_price);
      return true;
    },
  );
});
