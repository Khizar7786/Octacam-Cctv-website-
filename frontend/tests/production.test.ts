import assert from "node:assert/strict";
import { spawn, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { access } from "node:fs/promises";
import { createServer, type AddressInfo } from "node:net";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createRequestHandler, type ServerBuild } from "react-router";

const frontendRoot = fileURLToPath(new URL("../", import.meta.url));
const buildUrl = new URL("../build/server/index.js", import.meta.url);
let server: ChildProcess | undefined;
let baseUrl: string;
let output = "";

before(async () => {
  await access(buildUrl).catch(() => {
    throw new Error("Run npm run build before npm run test:production.");
  });
  const socket = createServer();
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
    env: { ...process.env, HOST: "127.0.0.1", PORT: String(port), NODE_ENV: "production" },
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
});

test("production serves SSR documents on direct and refreshed nested requests", async () => {
  for (const path of ["/", "/foundation", "/foundation"]) {
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
      assert.match(html, /Server-rendered route loaded successfully\./);
    } else {
      assert.match(html, /OctaCam is in development/);
    }
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
