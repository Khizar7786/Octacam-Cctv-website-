import assert from "node:assert/strict";
import { spawn, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { access, readFile, readdir } from "node:fs/promises";
import { createServer as createHttpServer, type Server as HttpServer } from "node:http";
import { createServer as createNetServer, type AddressInfo } from "node:net";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createMemoryRouter, createRequestHandler, type ServerBuild } from "react-router";
import { plannedPages } from "../app/config/storefront.ts";

const frontendRoot = fileURLToPath(new URL("../", import.meta.url));
const buildUrl = new URL("../build/server/index.js", import.meta.url);
let server: ChildProcess | undefined;
let apiServer: HttpServer | undefined;
let baseUrl: string;
let apiOrigin: string;
let output = "";
let catalogStatus = 200;
let catalogReply: unknown = { count: 0, next: null, previous: null, results: [] };
let catalogResponder: ((path: string) => unknown) | null = null;
const taxonomy = (id: number, name: string, slug: string, is_active = true) => ({
  id, name, slug, description: "", is_active, sort_order: id,
  created_at: "2026-10-05T00:00:00Z", updated_at: "2026-10-05T00:00:00Z",
});
let brands = [taxonomy(1, "Hikvision", "hikvision"), taxonomy(2, "Dahua", "dahua")];
const categories = [taxonomy(1, "Cameras", "cameras"), taxonomy(2, "Recorders", "recorders"), taxonomy(3, "Storage", "storage"), taxonomy(4, "Accessories", "accessories")];

before(async () => {
  await access(buildUrl).catch(() => {
    throw new Error("Run npm run build before npm run test:production.");
  });
  apiServer = createHttpServer((request, response) => {
    if (request.url?.startsWith("/api/v1/catalog/products/")) {
      const productQuery = new URL(request.url, "http://localhost").searchParams;
      if (productQuery.get("category") === "storage" && productQuery.has("spec_resolution")) {
        response.writeHead(400, { "Content-Type": "application/json" });
        response.end(JSON.stringify({ error: { code: "VALIDATION_ERROR", message: "Invalid filters.", fields: { spec_resolution: ["No active filterable specification for this category."] } } }));
        return;
      }
      response.writeHead(catalogStatus, { "Content-Type": "application/json" });
      response.end(JSON.stringify(catalogResponder ? catalogResponder(request.url ?? "") : catalogReply));
      return;
    }
    const url = new URL(request.url ?? "/", "http://localhost");
    const taxonomyMatch = url.pathname.match(/^\/api\/v1\/catalog\/(brands|categories)\/(?:([^/]+)\/)?$/);
    if (taxonomyMatch) {
      const items = (taxonomyMatch[1] === "brands" ? brands : categories).filter((item) => item.is_active);
      const detail = taxonomyMatch[2] ? items.find((item) => item.slug === taxonomyMatch[2]) : null;
      const pageNumber = Number(url.searchParams.get("page") ?? "1");
      const page = taxonomyMatch[2] ? detail : Number.isSafeInteger(pageNumber) && pageNumber > 0 && (pageNumber === 1 || (pageNumber - 1) * 20 < items.length) ? {
        count: items.length,
        next: pageNumber * 20 < items.length ? `http://internal-backend:8000${url.pathname}?page=${pageNumber + 1}` : null,
        previous: pageNumber > 1 ? `http://internal-backend:8000${url.pathname}${pageNumber === 2 ? "" : `?page=${pageNumber - 1}`}` : null,
        results: items.slice((pageNumber - 1) * 20, pageNumber * 20),
      } : null;
      response.writeHead(page ? 200 : 404, { "Content-Type": "application/json" });
      response.end(JSON.stringify(page ?? { error: { code: "NOT_FOUND", message: "Not found.", fields: {} } }));
      return;
    }
    if (url.pathname === "/api/v1/catalog/filters/") {
      const specifications = url.searchParams.get("category") === "cameras" ? [
        { key: "resolution", label: "Resolution", type: "choice", unit: null, options: [{ value: "2mp", label: "2 MP" }, { value: "4mp", label: "4 MP" }] },
        { key: "outdoor", label: "Outdoor use", type: "boolean", unit: null, options: [{ value: true, label: "Yes" }, { value: false, label: "No" }] },
        { key: "ir_distance", label: "IR distance", type: "decimal_range", unit: "m", min: "20.0000", max: "50.0000" },
      ] : url.searchParams.get("category") === "storage" ? [
        { key: "capacity", label: "Capacity", type: "integer_range", unit: "TB", min: "1", max: "4" },
      ] : [];
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({
        brand: brands.filter((item) => item.is_active).map((item) => ({ value: item.slug, label: item.name })),
        category: categories.filter((item) => item.is_active).map((item) => ({ value: item.slug, label: item.name })),
        price: { min: null, max: null }, specifications,
      }));
      return;
    }
    response.writeHead(404, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ error: { code: "NOT_FOUND", message: "Not found.", fields: {} } }));
  });
  apiServer.listen(0, "127.0.0.1");
  await once(apiServer, "listening");
  const apiPort = (apiServer.address() as AddressInfo).port;
  apiOrigin = `http://127.0.0.1:${apiPort}`;

  const socket = createNetServer();
  socket.listen(0, "127.0.0.1");
  await once(socket, "listening");
  const port = (socket.address() as AddressInfo).port;
  await new Promise<void>((resolve, reject) => socket.close((error) => error ? reject(error) : resolve()));
  baseUrl = `http://127.0.0.1:${port}`;

  server = spawn(process.execPath, [
    fileURLToPath(new URL("../node_modules/@react-router/serve/bin.js", import.meta.url)),
    fileURLToPath(buildUrl),
  ], {
    cwd: frontendRoot,
    env: {
      ...process.env,
      HOST: "127.0.0.1",
      PORT: String(port),
      NODE_ENV: "production",
      OCTACAM_API_ORIGIN: apiOrigin,
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  server.stdout?.on("data", (chunk: Buffer) => { output += chunk.toString(); });
  server.stderr?.on("data", (chunk: Buffer) => { output += chunk.toString(); });
  let startError: Error | undefined;
  server.on("error", (error) => { startError = error; });

  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    if (startError || server.exitCode !== null) {
      throw new Error(`Production server exited: ${startError?.message ?? output}`);
    }
    try {
      const response = await fetch(baseUrl, { signal: AbortSignal.timeout(1000) });
      await response.text();
      if (response.status === 200) return;
    } catch {
      // The process is still starting; keep the bounded readiness check running.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Production server did not become ready: ${output}`);
}, { timeout: 25_000 });

after(async () => {
  if (server && server.exitCode === null && server.signalCode === null) {
    const exited = once(server, "exit");
    server.kill();
    await exited;
  }
  if (apiServer) {
    await new Promise<void>((resolve, reject) => apiServer?.close((error) => error ? reject(error) : resolve()));
  }
});

test("production serves SSR documents on direct and refreshed nested requests", async () => {
  for (const path of ["/", "/foundation", "/foundation", "/visual-foundation", "/shop", "/shop", "/search"]) {
    const response = await fetch(`${baseUrl}${path}`);
    const html = await response.text();
    assert.equal(response.status, 200);
    assert.match(response.headers.get("content-type") ?? "", /text\/html/);
    assert.match(response.headers.get("x-robots-tag") ?? "", /noindex/);
    assert.match(response.headers.get("cache-control") ?? "", /no-store/);
    assert.match(html, /<html lang="en"/);
    assert.match(html, /<h1[^>]*>/);
    assert.match(html, /Skip to content/);
    if (path === "/foundation") {
      assert.match(html, /public catalog was loaded by the server API client during SSR/i);
      assert.match(html, /live catalog currently has no published products/i);
    } else if (path === "/visual-foundation") {
      assert.match(html, /Built for clear decisions/);
      assert.match(html, /src="\/brand\/octacam-logo\.png"/);
      assert.match(html, /Buttons and fields/);
    } else if (path === "/shop" || path === "/search") {
      assert.match(html, path === "/shop" ? /Shop CCTV equipment/ : /Search CCTV equipment/);
      assert.match(html, /No published products yet/);
    } else {
      assert.match(html, /Build around the equipment you need/);
    }
  }
});

test("shop renders published catalog cards and backend pagination in initial HTML", async () => {
  const saleProduct = {
    id: 11,
    brand: { id: 1, name: "Hikvision", slug: "hikvision" },
    category: { id: 2, name: "Cameras", slug: "cameras" },
    sku: "CAM-11", slug: "cam-11", name: "Published sale camera", short_description: "Recorded by staff",
    regular_price: "12000.00", sale_price: "9999.00", selling_price: "9999.00",
    stock_quantity: 4, is_in_stock: true, primary_image: null,
  };
  const zeroStockProduct = {
    ...saleProduct,
    id: 12, sku: "DRV-12", slug: "drv-12", name: "Published zero-stock recorder",
    category: { id: 3, name: "Recorders", slug: "recorders" },
    regular_price: "5000.00", sale_price: "5000.00", selling_price: "5000.00",
    stock_quantity: 0, is_in_stock: false,
    primary_image: {
      id: 9, image_url: "/media/products/recorder.webp", alt_text: "Front of recorder",
      sort_order: 0, width: 640, height: 480, created_at: "2026-10-05T00:00:00Z",
    },
  };
  const remainingFirstPage = Array.from({ length: 18 }, (_, index) => ({
    ...saleProduct,
    id: 20 + index, sku: `ACC-${20 + index}`, slug: `acc-${20 + index}`, name: `Published accessory ${20 + index}`,
    regular_price: "1000.00", sale_price: null, selling_price: "1000.00", primary_image: null,
  }));
  catalogResponder = (path) => path.includes("page=2")
    ? { count: 21, next: null, previous: "http://internal-backend:8000/api/v1/catalog/products/", results: [{ ...saleProduct, id: 13, sku: "ACC-13", slug: "acc-13", name: "Published accessory 13" }] }
    : { count: 21, next: "http://internal-backend:8000/api/v1/catalog/products/?page=2", previous: null, results: [saleProduct, zeroStockProduct, ...remainingFirstPage] };
  try {
    const firstResponse = await fetch(`${baseUrl}/shop`);
    const first = (await firstResponse.text()).split("<script")[0];
    assert.equal(firstResponse.status, 200);
    assert.match(first, /Published sale camera/);
    assert.match(first, /Published zero-stock recorder/);
    assert.match(first, /Model\/SKU:(?:\s|<!-- -->)*CAM-11/);
    assert.match(first, /PKR(?:\s|<!-- -->)*9999\.00/);
    assert.match(first, /Regular price:/);
    assert.equal((first.match(/<s>/g) ?? []).length, 1, "only the lower valid sale has a struck regular price");
    assert.match(first, /Out of stock/);
    assert.match(first, /Image unavailable/);
    assert.match(first, /alt="Front of recorder"/);
    assert.match(first, /href="\/shop\?page=2"/);
    assert.doesNotMatch(first, /Free shipping|Warranty included|Add to cart/);

    const secondResponse = await fetch(`${baseUrl}/shop?page=2`);
    const second = (await secondResponse.text()).split("<script")[0];
    assert.equal(secondResponse.status, 200);
    assert.match(second, /Published accessory 13/);
    assert.doesNotMatch(second, /Published zero-stock recorder/);
    assert.match(second, /Page(?:\s|<!-- -->)*2/);
    assert.match(second, /Previous page/);
    assert.match(second, /href="\/shop"/);
    assert.doesNotMatch(second, /Next page/);
  } finally {
    catalogResponder = null;
  }
});

test("shop handles empty, invalid-page, and catalog-error states without invented products", async () => {
  const empty = (await (await fetch(`${baseUrl}/shop`)).text()).split("<script")[0];
  assert.match(empty, /No published products yet/);
  assert.doesNotMatch(empty, /<article/);

  for (const path of ["/shop?page=0", "/shop?unsupported=option"]) {
    const invalid = (await (await fetch(`${baseUrl}${path}`)).text()).split("<script")[0];
    assert.match(invalid, /This catalog selection is unavailable/);
    assert.match(invalid, /Return to page 1/);
  }

  const noMatch = (await (await fetch(`${baseUrl}/shop?q=unimplemented`)).text()).split("<script")[0];
  assert.match(noMatch, /Results for “unimplemented”/);
  assert.match(noMatch, /No matching products/);

  catalogStatus = 404;
  catalogReply = { error: { code: "NOT_FOUND", message: "Invalid page.", fields: {} } };
  try {
    const invalid = (await (await fetch(`${baseUrl}/shop?page=999`)).text()).split("<script")[0];
    assert.match(invalid, /This catalog selection is unavailable/);
  } finally {
    catalogStatus = 200;
    catalogReply = { count: 0, next: null, previous: null, results: [] };
  }

  catalogStatus = 503;
  catalogReply = { error: { code: "CATALOG_UNAVAILABLE", message: "Unavailable", fields: {} } };
  try {
    const error = (await (await fetch(`${baseUrl}/shop`)).text()).split("<script")[0];
    assert.match(error, /Products could not be loaded/);
    assert.match(error, /Try again/);
    assert.doesNotMatch(error, /<article/);
  } finally {
    catalogStatus = 200;
    catalogReply = { count: 0, next: null, previous: null, results: [] };
  }
});

test("search SSR preserves query, filters, sort, and scope across product pages", async () => {
  const product = {
    id: 301, brand: { id: 1, name: "Hikvision", slug: "hikvision" },
    category: { id: 1, name: "Cameras", slug: "cameras" },
    sku: "DS-2CE", slug: "ds-2ce", name: "Published camera model", short_description: "Public search fixture",
    regular_price: "9000.00", sale_price: null, selling_price: "9000.00",
    stock_quantity: 1, is_in_stock: true, primary_image: null,
  };
  const seenQueries: URLSearchParams[] = [];
  catalogResponder = (path) => {
    const search = new URL(path, "http://localhost").searchParams;
    seenQueries.push(search);
    if (search.get("q") === "missing") return { count: 0, next: null, previous: null, results: [] };
    if (search.get("q") === "DS-2CE") {
      const second = search.get("page") === "2";
      return {
        count: 21,
        next: second ? null : "http://internal-backend:8000/api/v1/catalog/products/?page=2&q=DS-2CE",
        previous: second ? "http://internal-backend:8000/api/v1/catalog/products/?q=DS-2CE" : null,
        results: [product],
      };
    }
    return { count: 0, next: null, previous: null, results: [] };
  };
  try {
    const query = "q=DS-2CE&brand=hikvision&category=cameras&min_price=5000.00&max_price=10000.00&availability=in_stock&sort=price_asc";
    const first = await fetch(`${baseUrl}/search?${query}`);
    const firstHtml = (await first.text()).split("<script")[0];
    assert.equal(first.status, 200);
    assert.match(firstHtml, /Search results for DS-2CE \| OctaCam/);
    assert.match(firstHtml, /Results for “DS-2CE”/);
    assert.match(firstHtml, /Published camera model/);
    assert.match(firstHtml, /Model\/SKU:(?:\s|<!-- -->)*DS-2CE/);
    assert.match(firstHtml, /21(?:\s|<!-- -->)*products/);
    assert.match(firstHtml, /Remove Brand: Hikvision filter/);
    assert.match(firstHtml, /Remove Category: Cameras filter/);
    assert.match(firstHtml, /Remove From PKR 5000\.00 filter/);
    assert.match(firstHtml, /href="\/search\?q=DS-2CE&amp;brand=hikvision&amp;category=cameras&amp;min_price=5000\.00&amp;max_price=10000\.00&amp;availability=in_stock&amp;sort=price_asc&amp;page=2"/);
    assert.equal(seenQueries.at(-1)?.get("q"), "DS-2CE");
    assert.equal(seenQueries.at(-1)?.get("sort"), "price_asc");
    assert.equal(seenQueries.at(-1)?.get("min_price"), "5000.00");

    const refreshed = (await (await fetch(`${baseUrl}/search?${query}`)).text()).split("<script")[0];
    assert.match(refreshed, /Results for “DS-2CE”/);
    assert.match(refreshed, /Remove Brand: Hikvision filter/);
    assert.match(refreshed, /Published camera model/);

    const second = (await (await fetch(`${baseUrl}/search?${query}&page=2`)).text()).split("<script")[0];
    assert.match(second, /Page(?:\s|<!-- -->)*2/);
    assert.match(second, /href="\/search\?q=DS-2CE&amp;brand=hikvision&amp;category=cameras&amp;min_price=5000\.00&amp;max_price=10000\.00&amp;availability=in_stock&amp;sort=price_asc"/);

    const zero = (await (await fetch(`${baseUrl}/search?q=missing&brand=hikvision`)).text()).split("<script")[0];
    assert.match(zero, /Results for “missing”/);
    assert.match(zero, /No matching products/);
    assert.match(zero, /href="\/search\?q=missing"/);
    assert.match(zero, /href="\/#categories"/);
    assert.doesNotMatch(zero, /<article/);
  } finally {
    catalogResponder = null;
  }
});

test("technical filters render by category and preserve combined query on SSR reload and pagination", async () => {
  const seenQueries: URLSearchParams[] = [];
  catalogResponder = (path) => {
    const search = new URL(path, "http://localhost").searchParams;
    seenQueries.push(search);
    if (search.get("spec_resolution") === "unobserved-active-choice") return { count: 0, next: null, previous: null, results: [] };
    return {
      count: 21,
      next: search.get("page") === "2" ? null : "http://internal-backend:8000/api/v1/catalog/products/?page=2",
      previous: search.get("page") === "2" ? "http://internal-backend:8000/api/v1/catalog/products/" : null,
      results: [],
    };
  };
  try {
    const query = "q=DS-2CE&category=cameras&brand=hikvision&spec_resolution=2mp&spec_outdoor=true&spec_ir_distance_min=20.0000&spec_ir_distance_max=25&sort=price_asc";
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const response = await fetch(`${baseUrl}/search?${query}`);
      const html = (await response.text()).split("<script")[0];
      assert.equal(response.status, 200);
      assert.match(html, /Technical specifications/);
      assert.match(html, /Resolution/);
      assert.match(html, /Outdoor use/);
      assert.match(html, /IR distance/);
      assert.match(html, /Remove Resolution: 2 MP filter/);
      assert.match(html, /Remove Outdoor use: Yes filter/);
      assert.match(html, /spec_ir_distance_max=25&amp;spec_ir_distance_min=20\.0000&amp;spec_outdoor=true&amp;spec_resolution=2mp&amp;sort=price_asc&amp;page=2/);
      assert.equal(seenQueries.at(-1)?.get("spec_resolution"), "2mp");
      assert.equal(seenQueries.at(-1)?.get("spec_outdoor"), "true");
      assert.equal(seenQueries.at(-1)?.get("spec_ir_distance_min"), "20.0000");
    }
    const pageTwo = (await (await fetch(`${baseUrl}/search?${query}&page=2`)).text()).split("<script")[0];
    assert.match(pageTwo, /Remove Resolution: 2 MP filter/);
    assert.match(pageTwo, /Page(?:\s|<!-- -->)*2/);

    const categoryPage = (await (await fetch(`${baseUrl}/categories/cameras?spec_resolution=2mp&spec_ir_distance_min=20`)).text()).split("<script")[0];
    assert.match(categoryPage, /Remove Resolution: 2 MP filter/);
    assert.match(categoryPage, /href="\/categories\/cameras\?spec_ir_distance_min=20&amp;spec_resolution=2mp&amp;page=2"/);
    assert.equal(seenQueries.at(-1)?.get("category"), "cameras");

    const storage = (await (await fetch(`${baseUrl}/search?category=storage&spec_capacity_min=2&spec_capacity_max=3`)).text()).split("<script")[0];
    assert.match(storage, /Capacity \(TB\)/);
    assert.doesNotMatch(storage, /IR distance/);
    assert.doesNotMatch(storage, /Outdoor use/);
    assert.equal(seenQueries.at(-1)?.get("spec_capacity_min"), "2");

    const unobserved = (await (await fetch(`${baseUrl}/search?category=cameras&spec_resolution=unobserved-active-choice`)).text()).split("<script")[0];
    assert.match(unobserved, /No matching products/);
    assert.equal(seenQueries.at(-1)?.get("spec_resolution"), "unobserved-active-choice");

    const priorCalls = seenQueries.length;
    const incompatible = (await (await fetch(`${baseUrl}/search?category=storage&spec_resolution=2mp`)).text()).split("<script")[0];
    assert.equal(seenQueries.length, priorCalls);
    assert.match(incompatible, /No active filterable specification for this category/);
    assert.match(incompatible, /Remove resolution: 2mp filter/);
  } finally {
    catalogResponder = null;
  }
});

test("invalid search prices retain entered values and avoid a catalog request", async () => {
  let calls = 0;
  catalogResponder = () => { calls += 1; return { count: 0, next: null, previous: null, results: [] }; };
  try {
    const response = await fetch(`${baseUrl}/search?q=DS-2CE&min_price=100.00&max_price=50.00`);
    const html = (await response.text()).split("<script")[0];
    assert.equal(response.status, 200);
    assert.match(html, /Maximum price must be at least minimum price/);
    assert.match(html, /value="DS-2CE"/);
    assert.match(html, /value="100.00"/);
    assert.match(html, /value="50.00"/);
    assert.match(html, /aria-invalid="true"/);
    assert.match(html, /Start a new search/);
    assert.equal(calls, 0);
  } finally {
    catalogResponder = null;
  }
});

test("unknown filter values have a recoverable state without a false result claim", async () => {
  const response = await fetch(`${baseUrl}/search?q=DS-2CE&brand=no-such-brand`);
  const html = (await response.text()).split("<script")[0];
  assert.equal(response.status, 200);
  assert.match(html, /This brand is unavailable/);
  assert.match(html, /Start a new search/);
  assert.doesNotMatch(html, /No matching products/);
});

test("All Brands and scoped brand/category pages render active data in initial HTML", async () => {
  const product = {
    id: 101, brand: { id: 1, name: "Hikvision", slug: "hikvision" },
    category: { id: 1, name: "Cameras", slug: "cameras" },
    sku: "CAM-101", slug: "cam-101", name: "Published scope camera", short_description: "Public fixture",
    regular_price: "12000.00", sale_price: null, selling_price: "12000.00",
    stock_quantity: 0, is_in_stock: false, primary_image: null,
  };
  const seenScope: URLSearchParams[] = [];
  catalogResponder = (path) => {
    const query = new URL(path, "http://localhost").searchParams;
    seenScope.push(query);
    if (query.get("brand") === "hikvision" || query.get("category") === "cameras") {
      return query.get("page") === "2"
        ? { count: 21, next: null, previous: "http://internal-backend:8000/api/v1/catalog/products/?brand=hikvision&category=cameras", results: [product] }
        : { count: 21, next: "http://internal-backend:8000/api/v1/catalog/products/?page=2&brand=hikvision&category=cameras", previous: null, results: [product] };
    }
    return { count: 0, next: null, previous: null, results: [] };
  };
  try {
    const all = await fetch(`${baseUrl}/brands`);
    const allHtml = (await all.text()).split("<script")[0];
    assert.equal(all.status, 200);
    assert.match(allHtml, /All CCTV brands \| OctaCam/);
    assert.match(allHtml, /2(?:\s|<!-- -->)*brands/);
    assert.match(allHtml, /href="\/brands\/hikvision"/);
    assert.match(allHtml, /href="\/brands\/dahua"/);

    const brand = await fetch(`${baseUrl}/brands/hikvision?category=cameras`);
    const brandHtml = (await brand.text()).split("<script")[0];
    assert.equal(brand.status, 200);
    assert.match(brandHtml, /Hikvision CCTV equipment \| OctaCam/);
    assert.match(brandHtml, /aria-label="Breadcrumb"/);
    assert.match(brandHtml, /21(?:\s|<!-- -->)*products/);
    assert.match(brandHtml, /Published scope camera/);
    assert.match(brandHtml, /Out of stock/);
    assert.match(brandHtml, /name="category"/);
    assert.match(brandHtml, /href="\/brands\/hikvision\?category=cameras&amp;page=2"/);

    const brandFiltered = (await (await fetch(`${baseUrl}/brands/hikvision?category=cameras&min_price=5000.00&availability=in_stock&sort=price_desc`)).text()).split("<script")[0];
    assert.match(brandFiltered, /name="category"/);
    assert.doesNotMatch(brandFiltered, /name="brand"/);
    assert.match(brandFiltered, /href="\/brands\/hikvision\?category=cameras&amp;min_price=5000.00&amp;availability=in_stock&amp;sort=price_desc&amp;page=2"/);
    assert.equal(seenScope.at(-1)?.get("brand"), "hikvision");
    assert.equal(seenScope.at(-1)?.get("category"), "cameras");
    assert.equal(seenScope.at(-1)?.get("min_price"), "5000.00");

    const category = await fetch(`${baseUrl}/categories/cameras?brand=hikvision`);
    const categoryHtml = (await category.text()).split("<script")[0];
    assert.equal(category.status, 200);
    assert.match(categoryHtml, /Cameras \| OctaCam CCTV equipment/);
    assert.match(categoryHtml, /name="brand"/);
    assert.match(categoryHtml, /Published scope camera/);
    assert.match(categoryHtml, /href="\/categories\/cameras\?brand=hikvision&amp;page=2"/);
    const categoryFiltered = (await (await fetch(`${baseUrl}/categories/cameras?brand=hikvision&max_price=12000.00&sort=price_asc`)).text()).split("<script")[0];
    assert.match(categoryFiltered, /name="brand"/);
    assert.doesNotMatch(categoryFiltered, /name="category"/);
    assert.match(categoryFiltered, /href="\/categories\/cameras\?brand=hikvision&amp;max_price=12000.00&amp;sort=price_asc&amp;page=2"/);
    assert.equal(seenScope.at(-1)?.get("category"), "cameras");
    assert.equal(seenScope.at(-1)?.get("max_price"), "12000.00");
    const next = await fetch(`${baseUrl}/categories/cameras?brand=hikvision&page=2`);
    const nextHtml = (await next.text()).split("<script")[0];
    assert.match(nextHtml, /Page(?:\s|<!-- -->)*2/);
    assert.match(nextHtml, /href="\/categories\/cameras\?brand=hikvision"/);
  } finally {
    catalogResponder = null;
  }
});

test("active empty taxonomy differs from inactive, unknown, and invalid selections", async () => {
  brands.push(taxonomy(3, "Empty Brand", "empty-brand"), taxonomy(4, "Hidden Brand", "hidden-brand", false));
  try {
    const empty = await fetch(`${baseUrl}/brands/empty-brand`);
    const emptyHtml = (await empty.text()).split("<script")[0];
    assert.equal(empty.status, 200);
    assert.match(emptyHtml, /No published products in this selection/);
    assert.match(emptyHtml, /0(?:\s|<!-- -->)*products/);

    for (const path of ["/brands/hidden-brand", "/brands/no-such-brand", "/categories/no-such-category"]) {
      const response = await fetch(`${baseUrl}${path}`);
      assert.equal(response.status, 404, path);
      assert.match(await response.text(), /Page not found/);
    }
    const invalid = await fetch(`${baseUrl}/brands/hikvision?category=no-such-category`);
    assert.equal(invalid.status, 200);
    assert.match(await invalid.text(), /This catalog selection is unavailable/);

    const all = (await (await fetch(`${baseUrl}/brands`)).text()).split("<script")[0];
    assert.match(all, /href="\/brands\/empty-brand"/);
    assert.doesNotMatch(all, /href="\/brands\/hidden-brand"/);
  } finally {
    brands = brands.filter((brand) => ![3, 4].includes(brand.id));
  }
});

test("All Brands follows backend pagination without changing the brand destination", async () => {
  const additional = Array.from({ length: 19 }, (_, index) => taxonomy(100 + index, `Brand ${index + 1}`, `brand-${index + 1}`));
  brands.push(...additional);
  try {
    const first = (await (await fetch(`${baseUrl}/brands`)).text()).split("<script")[0];
    assert.match(first, /21(?:\s|<!-- -->)*brands/);
    assert.match(first, /href="\/brands\?page=2"/);
    const second = (await (await fetch(`${baseUrl}/brands?page=2`)).text()).split("<script")[0];
    assert.match(second, /Brand 19/);
    assert.match(second, /href="\/brands"/);
    assert.doesNotMatch(second, /Next page/);
  } finally {
    brands = brands.filter((brand) => brand.id < 100);
  }
});

test("product-card destination is an honest placeholder until detail pages exist", async () => {
  const response = await fetch(`${baseUrl}/products/cam-11`);
  const html = (await response.text()).split("<script")[0];
  assert.equal(response.status, 200);
  assert.match(html, /Product details are coming soon/);
  assert.match(html, /Return to shop/);
  assert.match(response.headers.get("x-robots-tag") ?? "", /noindex/);
});

test("homepage renders its first promotion and static sections without catalog records", async () => {
  const html = await (await fetch(baseUrl)).text();
  assert.match(html, /Build around the equipment you need/);
  assert.doesNotMatch(html, /Planning a CCTV setup in Lahore\?/);
  assert.match(html, /href="\/#categories"/);
  assert.match(html, /id="categories"/);
  assert.match(html, /id="lahore-survey"/);
  assert.match(html, /Hikvision/);
  assert.match(html, /Dahua/);
  assert.match(html, /Cash on delivery/);
  assert.doesNotMatch(html, /id="published-products"/);
  assert.match(html, /Previous promotion/);
  assert.match(html, /Next promotion/);
  for (const path of ["equipment-desktop.svg", "equipment-mobile.svg", "survey-desktop.svg", "survey-mobile.svg"]) {
    const response = await fetch(`${baseUrl}/promotions/${path}`);
    assert.equal(response.status, 200, path);
    assert.match(response.headers.get("content-type") ?? "", /image\/svg\+xml/, path);
  }
});

test("homepage shows only genuine public catalog records with server-provided money", async () => {
  catalogReply = {
    count: 1, next: null, previous: null,
    results: [{
      id: 7,
      brand: { id: 1, name: "Hikvision", slug: "hikvision" },
      category: { id: 2, name: "Cameras", slug: "cameras" },
      sku: "MODEL-7",
      slug: "model-7",
      name: "Published camera",
      short_description: "Public API fixture",
      regular_price: "15000.00",
      sale_price: null,
      selling_price: "15000.00",
      stock_quantity: 0,
      is_in_stock: false,
      primary_image: null,
    }],
  };
  try {
    const html = await (await fetch(baseUrl)).text();
    assert.match(html, /id="published-products"/);
    assert.match(html, /Published camera/);
    assert.match(html, /MODEL-7/);
    assert.match(html, /PKR(?:\s|<!-- -->)*15000\.00/);
    assert.match(html, /Out of stock/);
    assert.match(html, /Image unavailable/);
    assert.doesNotMatch(html, /Add to cart/);
  } finally {
    catalogReply = { count: 0, next: null, previous: null, results: [] };
  }
});

test("catalog failure leaves the SSR homepage usable with an honest status", async () => {
  catalogStatus = 503;
  catalogReply = { error: { code: "CATALOG_UNAVAILABLE", message: "Unavailable", fields: {} } };
  try {
    const response = await fetch(baseUrl);
    const html = await response.text();
    assert.equal(response.status, 200);
    assert.match(html, /The product catalog is unavailable right now/);
    assert.match(html, /Need help planning your system\?/);
    assert.doesNotMatch(html, /id="published-products"/);
  } finally {
    catalogStatus = 200;
    catalogReply = { count: 0, next: null, previous: null, results: [] };
  }
});

test("the production server serves the approved transparent logo", async () => {
  const response = await fetch(`${baseUrl}/brand/octacam-logo.png`);
  const image = Buffer.from(await response.arrayBuffer());
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /image\/png/);
  assert.equal(image.readUInt32BE(16), 1254);
  assert.equal(image.readUInt32BE(20), 1254);
  assert.equal(image[25], 6);
});

test("shared navigation exposes honest, non-indexed destinations without unverified contact links", async () => {
  const home = await (await fetch(baseUrl)).text();
  assert.match(home, /aria-label="Storefront"/);
  assert.match(home, /aria-label="Mobile storefront"/);
  assert.match(home, /Details pending verification/);
  assert.doesNotMatch(home, /href="(?:mailto:|tel:|https:\/\/wa\.me\/)/);

  for (const page of plannedPages) {
    const response = await fetch(`${baseUrl}${page.to}`);
    const html = await response.text();
    assert.equal(response.status, 200, page.to);
    assert.match(response.headers.get("x-robots-tag") ?? "", /noindex/, page.to);
    assert.match(html, /is coming soon/, page.to);
  }
});

test("the browser build contains no server-only API configuration", async () => {
  const clientRoot = fileURLToPath(new URL("../build/client/", import.meta.url));
  const files = await listFiles(clientRoot);
  const contents = await Promise.all(files.map((file) => readFile(file, "utf8")));
  const browserBuild = contents.join("\n");

  assert.doesNotMatch(browserBuild, /OCTACAM_API_ORIGIN/);
  assert.doesNotMatch(browserBuild, /http:\/\/127\.0\.0\.1:8000/);
});

test("the compiled client route uses the same-origin API path during React Router navigation", async () => {
  const assetsRoot = fileURLToPath(new URL("../build/client/assets/", import.meta.url));
  const foundationFiles = (await readdir(assetsRoot))
    .filter((name) => /^foundation-.*\.js$/.test(name));
  assert.equal(foundationFiles.length, 1);
  const routeModule = await import(pathToFileURL(join(assetsRoot, foundationFiles[0])).href) as {
    clientLoader(args: { request: Request }): Promise<{
      source: "browser";
      products: { count: number };
    }>;
  };

  const nativeFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    assert.equal(input, "/api/v1/catalog/products/");
    return nativeFetch(`${apiOrigin}${String(input)}`, init);
  };
  const router = createMemoryRouter([
    { id: "home", path: "/" },
    { id: "foundation", path: "/foundation", loader: routeModule.clientLoader },
  ], { initialEntries: ["/"] });

  try {
    await router.navigate("/foundation");
    assert.equal(router.state.location.pathname, "/foundation");
    assert.equal(router.state.navigation.state, "idle");
    assert.deepEqual(router.state.loaderData.foundation, {
      source: "browser",
      products: { count: 0, next: null, previous: null, results: [] },
    });
  } finally {
    router.dispose();
    globalThis.fetch = nativeFetch;
  }
});

test("unknown nested URLs return a real 404 document with recovery", async () => {
  const response = await fetch(`${baseUrl}/missing/nested/page`);
  const html = await response.text();
  assert.equal(response.status, 404);
  assert.match(html, /Page not found/);
  assert.match(html, /Return home/);
  assert.match(response.headers.get("x-robots-tag") ?? "", /noindex/);
});

test("the production server also serves the built CSS and hydration JavaScript", async () => {
  const html = await (await fetch(baseUrl)).text();
  const css = html.match(/href="([^"\s]+\.css)"/)?.[1];
  const js = html.match(/\/assets\/[^"\s]+?\.js/)?.[0];
  assert.ok(css, "SSR document must reference built CSS");
  assert.ok(js, "SSR document must reference hydration JavaScript");
  for (const [path, contentType] of [[css, /text\/css/], [js, /(?:java|ecma)script/]] as const) {
    const response = await fetch(new URL(path, baseUrl));
    assert.equal(response.status, 200);
    assert.match(response.headers.get("content-type") ?? "", contentType);
    assert.ok((await response.text()).length > 0);
  }
});

test("an unexpected loader failure renders the production boundary without private details", async () => {
  // Inject failure into a copy of the built route in this test only. No error-test
  // endpoint or throwing loader is shipped in the application.
  const build = await import(buildUrl.href) as ServerBuild;
  const home = build.routes["routes/home"];
  assert.ok(home);
  let reportedError: unknown;
  const failingBuild: ServerBuild = {
    ...build,
    entry: {
      ...build.entry,
      module: {
        ...build.entry.module,
        handleError(error) { reportedError = error; },
      },
    },
    routes: {
      ...build.routes,
      "routes/home": {
        ...home,
        module: {
          ...home.module,
          loader() { throw new Error("fixture-private-server-detail"); },
        },
      },
    },
  };
  const response = await createRequestHandler(failingBuild, "production")(new Request("http://localhost/"));
  const html = await response.text();
  assert.equal(response.status, 500);
  assert.match(html, /Unable to load this page/);
  assert.match(html, /Return home/);
  assert.doesNotMatch(html, /fixture-private-server-detail/);
  assert.ok(reportedError instanceof Error);
  assert.equal(reportedError.message, "fixture-private-server-detail");
});

async function listFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? listFiles(path) : [path];
  }));
  return nested.flat();
}
