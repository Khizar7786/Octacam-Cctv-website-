import assert from "node:assert/strict";
import { test } from "node:test";
import {
  ApiError,
  apiPath,
  createApiClient,
} from "../app/lib/api/client.ts";
import {
  API_ORIGIN_ENV,
  DEFAULT_LOCAL_API_ORIGIN,
  getServerApiOrigin,
} from "../app/lib/api/server-config.server.ts";

test("normalizes the backend error envelope without discarding field errors", async () => {
  const body = {
    error: {
      code: "VALIDATION_ERROR",
      message: "Some fields need attention.",
      fields: { min_price: ["Enter a number."] },
    },
  };
  const client = createApiClient({
    fetch: async () => Response.json(body, { status: 400 }),
  });

  await assert.rejects(
    client.request(apiPath("/api/v1/catalog/products/?min_price=bad")),
    (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 400);
      assert.equal(error.code, "VALIDATION_ERROR");
      assert.equal(error.message, "Some fields need attention.");
      assert.deepEqual(error.fields, { min_price: ["Enter a number."] });
      assert.deepEqual(error.body, body);
      return true;
    },
  );
});

test("turns non-JSON failures into a safe API error", async () => {
  const client = createApiClient({
    fetch: async () => new Response("private reverse-proxy details", { status: 502 }),
  });

  await assert.rejects(client.request(apiPath("/api/v1/catalog/products/")), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 502);
    assert.equal(error.code, "UNEXPECTED_API_RESPONSE");
    assert.doesNotMatch(error.message, /private|proxy/i);
    return true;
  });
});

test("normalizes a response stream failure without exposing its details", async () => {
  const client = createApiClient({
    fetch: async () => new Response(new ReadableStream({
      start(controller) { controller.error(new TypeError("private upstream reset")); },
    })),
  });

  await assert.rejects(client.request(apiPath("/api/v1/catalog/products/")), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, null);
    assert.equal(error.code, "NETWORK_ERROR");
    assert.doesNotMatch(error.message, /private|upstream/i);
    return true;
  });
});

test("keeps browser requests relative and forwards cancellation", async () => {
  const controller = new AbortController();
  let requestedUrl: string | URL | Request | undefined;
  let requestedSignal: AbortSignal | null | undefined;
  const client = createApiClient({
    fetch: async (input, init) => {
      requestedUrl = input;
      requestedSignal = init?.signal;
      return await new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason), { once: true });
      });
    },
  });

  const request = client.request(apiPath("/api/v1/catalog/products/"), { signal: controller.signal });
  controller.abort(new DOMException("Navigation cancelled", "AbortError"));

  await assert.rejects(request, (error: unknown) => error instanceof DOMException && error.name === "AbortError");
  assert.equal(requestedUrl, "/api/v1/catalog/products/");
  assert.equal(requestedSignal, controller.signal);
});

test("server requests prepend only a validated origin", async () => {
  let requestedUrl: string | URL | Request | undefined;
  const client = createApiClient({
    origin: "http://backend-internal:8000",
    fetch: async (input) => {
      requestedUrl = input;
      return Response.json({ ok: true });
    },
  });

  await client.request(apiPath("/api/v1/catalog/products/?page=2"));
  assert.equal(requestedUrl, "http://backend-internal:8000/api/v1/catalog/products/?page=2");
  assert.equal(getServerApiOrigin({}), DEFAULT_LOCAL_API_ORIGIN);
  assert.equal(
    getServerApiOrigin({ [API_ORIGIN_ENV]: "https://django.internal.example" }),
    "https://django.internal.example",
  );
  assert.throws(
    () => getServerApiOrigin({ NODE_ENV: "production" }),
    /required in production/,
  );
  assert.throws(
    () => getServerApiOrigin({ [API_ORIGIN_ENV]: "https://example.com/api/v1/" }),
    /origin without a path/,
  );
});

test("rejects API paths that could leave the same-origin versioned boundary", () => {
  for (const value of [
    "https://example.com/api/v1/catalog/products/",
    "/api/v2/catalog/products/",
    "/api/v1/catalog/products/#fragment",
    "/api/v1\\catalog/products/",
  ]) {
    assert.throws(() => apiPath(value), /must start with \/api\/v1\//);
  }
});
