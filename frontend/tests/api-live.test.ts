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

test("a direct shop request renders the real published catalog state in initial HTML", async () => {
  const productsResponse = await fetch(`${frontendOrigin}/api/v1/catalog/products/`, {
    signal: AbortSignal.timeout(5_000),
  });
  const products = await productsResponse.json() as { count: number };
  const response = await fetch(`${frontendOrigin}/shop`, { signal: AbortSignal.timeout(5_000) });
  const visibleHtml = (await response.text()).split("<script")[0];

  assert.equal(response.status, 200);
  assert.match(visibleHtml, /Shop CCTV equipment/);
  if (products.count === 0) {
    assert.match(visibleHtml, /No published products yet/);
    assert.doesNotMatch(visibleHtml, /<article/);
  } else {
    assert.match(visibleHtml, /Published products/);
    assert.match(visibleHtml, /Model\/SKU:/);
    assert.match(visibleHtml, /PKR/);
  }
});

test("a direct product page follows the real published detail contract", async () => {
  const listing = await fetch(`${frontendOrigin}/api/v1/catalog/products/`, { signal: AbortSignal.timeout(5_000) });
  assert.equal(listing.status, 200);
  const products = await listing.json() as { results: { slug: string; sku: string }[] };
  const first = products.results[0];
  if (first) {
    const detail = await fetch(`${frontendOrigin}/api/v1/catalog/products/${encodeURIComponent(first.slug)}/`, { signal: AbortSignal.timeout(5_000) });
    assert.equal(detail.status, 200);
    const product = await detail.json() as { sku: string; selling_price: string; stock_quantity: number };
    const response = await fetch(`${frontendOrigin}/products/${encodeURIComponent(first.slug)}`, { signal: AbortSignal.timeout(5_000) });
    const html = (await response.text()).split("<script")[0];
    assert.equal(response.status, 200);
    assert.ok(html.includes(product.sku));
    assert.ok(html.includes(product.selling_price));
    assert.ok(html.includes(String(product.stock_quantity)) || product.stock_quantity === 0);
  } else {
    const response = await fetch(`${frontendOrigin}/products/octacam-no-such-product`, { signal: AbortSignal.timeout(5_000) });
    assert.equal(response.status, 404);
    assert.match(await response.text(), /Page not found/);
  }
});

test("the live search contract and direct SSR search route agree on result count", async () => {
  const query = "q=octacam-no-such-model&min_price=0.00&availability=in_stock&sort=price_asc";
  const productsResponse = await fetch(`${frontendOrigin}/api/v1/catalog/products/?${query}`, { signal: AbortSignal.timeout(5_000) });
  assert.equal(productsResponse.status, 200);
  const products = await productsResponse.json() as { count: number };
  const searchResponse = await fetch(`${frontendOrigin}/search?${query}`, { signal: AbortSignal.timeout(5_000) });
  const html = (await searchResponse.text()).split("<script")[0];
  assert.equal(searchResponse.status, 200);
  assert.match(html, /Search results for octacam-no-such-model/);
  assert.match(html, new RegExp(`${products.count}(?:\\s|<!-- -->)*products?`));
  assert.match(html, /Results for/);
  if (products.count === 0) assert.match(html, /No matching products/);
});

test("live brand and category routes agree with active public taxonomy", async () => {
  const [brandResponse, categoryResponse] = await Promise.all([
    fetch(`${frontendOrigin}/api/v1/catalog/brands/`, { signal: AbortSignal.timeout(5_000) }),
    fetch(`${frontendOrigin}/api/v1/catalog/categories/`, { signal: AbortSignal.timeout(5_000) }),
  ]);
  assert.equal(brandResponse.status, 200);
  assert.equal(categoryResponse.status, 200);
  const brands = await brandResponse.json() as { count: number; results: { name: string; slug: string }[] };
  const categories = await categoryResponse.json() as { count: number; results: { name: string; slug: string }[] };
  const allBrands = await fetch(`${frontendOrigin}/brands`, { signal: AbortSignal.timeout(5_000) });
  const allHtml = (await allBrands.text()).split("<script")[0];
  assert.equal(allBrands.status, 200);
  assert.match(allHtml, new RegExp(`${brands.count}(?:\\s|<!-- -->)*brands?`));
  if (brands.results[0]) {
    const brand = await fetch(`${frontendOrigin}/brands/${brands.results[0].slug}`, { signal: AbortSignal.timeout(5_000) });
    assert.equal(brand.status, 200);
    assert.match(await brand.text(), /Published products/);
  } else {
    assert.match(allHtml, /No active brands yet/);
  }
  if (categories.results[0]) {
    const category = await fetch(`${frontendOrigin}/categories/${categories.results[0].slug}`, { signal: AbortSignal.timeout(5_000) });
    assert.equal(category.status, 200);
    assert.match(await category.text(), /Published products/);
  }
  const unknown = await fetch(`${frontendOrigin}/brands/no-such-brand`, { signal: AbortSignal.timeout(5_000) });
  assert.equal(unknown.status, 404);
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
