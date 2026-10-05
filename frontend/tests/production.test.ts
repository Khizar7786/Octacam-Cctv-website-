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

before(async () => {
  await access(buildUrl).catch(() => {
    throw new Error("Run npm run build before npm run test:production.");
  });
  apiServer = createHttpServer((request, response) => {
    if (request.url?.startsWith("/api/v1/catalog/products/")) {
      response.writeHead(catalogStatus, { "Content-Type": "application/json" });
      response.end(JSON.stringify(catalogReply));
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
  for (const path of ["/", "/foundation", "/foundation", "/visual-foundation"]) {
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
    } else {
      assert.match(html, /Build around the equipment you need/);
    }
  }
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
