import assert from "node:assert/strict";
import { test } from "node:test";
import { AuthRuntime } from "../app/features/auth/runtime.ts";
import { ApiError, apiPath, createApiClient } from "../app/lib/api/client.ts";

const user = { id: 7, email: "buyer@example.com", full_name: "Buyer", phone: "", is_staff: false };
const session = (access: string) => ({ user, access });
const denied = () => Response.json({ error: { code: "AUTHENTICATION_REQUIRED", message: "Authentication required.", fields: {} } }, { status: 401 });

test("registration bootstraps CSRF once and never reads a refresh token from JSON", async () => {
  let csrfCalls = 0;
  const client = createApiClient({ fetch: async (input, init) => {
    const path = String(input);
    if (path.endsWith("/csrf/")) { csrfCalls++; return Response.json({ csrfToken: "csrf-one" }); }
    assert.equal(path, "/api/v1/auth/register/");
    assert.equal(new Headers(init?.headers).get("X-CSRFToken"), "csrf-one");
    assert.equal(init?.credentials, "same-origin");
    assert.deepEqual(JSON.parse(String(init?.body)), { email: user.email, full_name: user.full_name, password: "secret" });
    return Response.json({ ...session("new-access"), refresh: "ignored-by-runtime" }, { status: 201 });
  } });
  const runtime = new AuthRuntime(client);
  await Promise.all([runtime.csrfToken(), runtime.csrfToken()]);
  assert.deepEqual(await runtime.register({ email: user.email, full_name: user.full_name, password: "secret" }), user);
  assert.equal(csrfCalls, 1);
  assert.deepEqual(runtime.getState(), { status: "authenticated", user });
});

test("restores a session through CSRF and a rotating cookie without SSR-shared state", async () => {
  const calls: { path: string; method: string; credentials: RequestCredentials | undefined; csrf: string | null }[] = [];
  const client = createApiClient({ fetch: async (input, init) => {
    const path = String(input);
    const headers = new Headers(init?.headers);
    calls.push({ path, method: init?.method ?? "GET", credentials: init?.credentials, csrf: headers.get("X-CSRFToken") });
    if (path.endsWith("/csrf/")) return Response.json({ csrfToken: "csrf-one" });
    if (path.endsWith("/refresh/")) return Response.json(session("restored-access"));
    throw new Error(`Unexpected request: ${path}`);
  } });
  const first = new AuthRuntime(client);
  const second = new AuthRuntime(client);
  assert.deepEqual(first.getServerSnapshot(), { status: "loading" });
  assert.deepEqual(second.getState(), { status: "loading" });
  assert.deepEqual(await first.restore(), { status: "authenticated", user });
  assert.deepEqual(second.getState(), { status: "loading" });
  assert.deepEqual(calls, [
    { path: "/api/v1/auth/csrf/", method: "GET", credentials: "same-origin", csrf: null },
    { path: "/api/v1/auth/refresh/", method: "POST", credentials: "same-origin", csrf: "csrf-one" },
  ]);
});

test("concurrent expired bearer requests share one refresh and each retry once", async () => {
  let refreshCount = 0;
  let releaseRefresh!: (response: Response) => void;
  let refreshStarted!: () => void;
  const started = new Promise<void>((resolve) => { refreshStarted = resolve; });
  const protectedCalls: string[] = [];
  const client = createApiClient({ fetch: async (input, init) => {
    const path = String(input);
    if (path.endsWith("/csrf/")) return Response.json({ csrfToken: "csrf-one" });
    if (path.endsWith("/login/")) return Response.json(session("expired-access"));
    if (path.endsWith("/refresh/")) {
      refreshCount++;
      refreshStarted();
      return new Promise<Response>((resolve) => { releaseRefresh = resolve; });
    }
    const bearer = new Headers(init?.headers).get("Authorization") ?? "";
    protectedCalls.push(`${path}:${bearer}`);
    return bearer === "Bearer refreshed-access" ? Response.json({ path }) : denied();
  } });
  const runtime = new AuthRuntime(client);
  await runtime.login({ email: user.email, password: "secret" });
  const profile = runtime.requestAuthenticated<{ path: string }>(apiPath("/api/v1/account/profile/"));
  const orders = runtime.requestAuthenticated<{ path: string }>(apiPath("/api/v1/account/orders/"));
  await started;
  assert.equal(refreshCount, 1);
  releaseRefresh(Response.json(session("refreshed-access")));
  assert.deepEqual((await Promise.all([profile, orders])).map((item) => item.path), [
    "/api/v1/account/profile/", "/api/v1/account/orders/",
  ]);
  assert.deepEqual(protectedCalls, [
    "/api/v1/account/profile/:Bearer expired-access",
    "/api/v1/account/orders/:Bearer expired-access",
    "/api/v1/account/profile/:Bearer refreshed-access",
    "/api/v1/account/orders/:Bearer refreshed-access",
  ]);
  assert.equal(runtime.getState().status, "authenticated");
});

test("failed shared refresh leaves all expired requests unauthenticated", async () => {
  let refreshCount = 0;
  const client = createApiClient({ fetch: async (input) => {
    const path = String(input);
    if (path.endsWith("/csrf/")) return Response.json({ csrfToken: "csrf-one" });
    if (path.endsWith("/login/")) return Response.json(session("expired-access"));
    if (path.endsWith("/refresh/")) { refreshCount++; return denied(); }
    return denied();
  } });
  const runtime = new AuthRuntime(client);
  await runtime.login({ email: user.email, password: "secret" });
  const results = await Promise.allSettled([
    runtime.requestAuthenticated(apiPath("/api/v1/account/profile/")),
    runtime.requestAuthenticated(apiPath("/api/v1/account/orders/")),
  ]);
  assert.equal(refreshCount, 1);
  for (const result of results) {
    assert.equal(result.status, "rejected");
    assert.ok(result.reason instanceof ApiError);
    assert.equal(result.reason.status, 401);
  }
  assert.deepEqual(runtime.getState(), { status: "unauthenticated" });
});

test("a late expired response cannot start a second refresh after the first failed", async () => {
  let refreshCount = 0;
  let releaseLate!: (response: Response) => void;
  const client = createApiClient({ fetch: async (input) => {
    const path = String(input);
    if (path.endsWith("/csrf/")) return Response.json({ csrfToken: "csrf-one" });
    if (path.endsWith("/login/")) return Response.json(session("expired-access"));
    if (path.endsWith("/refresh/")) { refreshCount++; return denied(); }
    if (path.endsWith("/profile/")) return new Promise<Response>((resolve) => { releaseLate = resolve; });
    return denied();
  } });
  const runtime = new AuthRuntime(client);
  await runtime.login({ email: user.email, password: "secret" });
  const late = runtime.requestAuthenticated(apiPath("/api/v1/account/profile/"));
  const first = runtime.requestAuthenticated(apiPath("/api/v1/account/orders/"));
  await assert.rejects(first, ApiError);
  releaseLate(denied());
  await assert.rejects(late, ApiError);
  assert.equal(refreshCount, 1);
  assert.deepEqual(runtime.getState(), { status: "unauthenticated" });
});

test("a retried 401 does not start another refresh", async () => {
  let refreshCount = 0;
  let protectedCount = 0;
  const client = createApiClient({ fetch: async (input) => {
    const path = String(input);
    if (path.endsWith("/csrf/")) return Response.json({ csrfToken: "csrf-one" });
    if (path.endsWith("/login/")) return Response.json(session("expired-access"));
    if (path.endsWith("/refresh/")) { refreshCount++; return Response.json(session("new-access")); }
    protectedCount++;
    return denied();
  } });
  const runtime = new AuthRuntime(client);
  await runtime.login({ email: user.email, password: "secret" });
  await assert.rejects(runtime.requestAuthenticated(apiPath("/api/v1/account/profile/")), ApiError);
  assert.equal(refreshCount, 1);
  assert.equal(protectedCount, 2);
  assert.deepEqual(runtime.getState(), { status: "unauthenticated" });
});

test("logout clears only memory session and posts with CSRF and same-origin cookies", async () => {
  const savedCart = '[{"product_id":42,"quantity":2}]';
  const originalStorage = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  const storage = new Map([["octacam.cart.v1", savedCart]]);
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
    clear: () => storage.clear(),
  } });
  const requests: { path: string; authorization: string | null; csrf: string | null; credentials: RequestCredentials | undefined }[] = [];
  const client = createApiClient({ fetch: async (input, init) => {
    const path = String(input);
    const headers = new Headers(init?.headers);
    requests.push({ path, authorization: headers.get("Authorization"), csrf: headers.get("X-CSRFToken"), credentials: init?.credentials });
    if (path.endsWith("/csrf/")) return Response.json({ csrfToken: "csrf-one" });
    if (path.endsWith("/login/")) return Response.json(session("access-one"));
    if (path.endsWith("/logout/")) return new Response(null, { status: 204 });
    throw new Error(`Unexpected request: ${path}`);
  } });
  const runtime = new AuthRuntime(client);
  try {
    await runtime.login({ email: user.email, password: "secret" });
    await runtime.logout();
    assert.deepEqual(runtime.getState(), { status: "unauthenticated" });
    await assert.rejects(runtime.requestAuthenticated(apiPath("/api/v1/account/profile/")), (error: unknown) => error instanceof ApiError && error.status === 401);
    assert.equal(storage.get("octacam.cart.v1"), savedCart);
    assert.deepEqual(requests.map(({ path }) => path), ["/api/v1/auth/csrf/", "/api/v1/auth/login/", "/api/v1/auth/logout/"]);
    assert.deepEqual(requests[2], { path: "/api/v1/auth/logout/", authorization: null, csrf: "csrf-one", credentials: "same-origin" });
  } finally {
    if (originalStorage) Object.defineProperty(globalThis, "localStorage", originalStorage);
    else Reflect.deleteProperty(globalThis, "localStorage");
  }
});

test("logout waits for a pending login response before revoking its cookie", async () => {
  let releaseLogin!: (response: Response) => void;
  let loginStarted!: () => void;
  const started = new Promise<void>((resolve) => { loginStarted = resolve; });
  const paths: string[] = [];
  const client = createApiClient({ fetch: async (input) => {
    const path = String(input);
    paths.push(path);
    if (path.endsWith("/csrf/")) return Response.json({ csrfToken: "csrf-one" });
    if (path.endsWith("/login/")) {
      loginStarted();
      return new Promise<Response>((resolve) => { releaseLogin = resolve; });
    }
    if (path.endsWith("/logout/")) return new Response(null, { status: 204 });
    throw new Error(`Unexpected request: ${path}`);
  } });
  const runtime = new AuthRuntime(client);
  const login = runtime.login({ email: user.email, password: "secret" });
  await started;
  const logout = runtime.logout();
  assert.deepEqual(runtime.getState(), { status: "unauthenticated" });
  assert.equal(paths.filter((path) => path.endsWith("/logout/")).length, 0);
  releaseLogin(Response.json(session("late-access")));
  await assert.rejects(login, (error: unknown) => error instanceof ApiError && error.status === 401);
  await logout;
  assert.deepEqual(runtime.getState(), { status: "unauthenticated" });
  assert.deepEqual(paths, ["/api/v1/auth/csrf/", "/api/v1/auth/login/", "/api/v1/auth/logout/"]);
});

test("temporary restoration failure is retryable without claiming a signed-out user", async () => {
  let attempts = 0;
  const client = createApiClient({ fetch: async (input) => {
    const path = String(input);
    if (path.endsWith("/csrf/")) return Response.json({ csrfToken: "csrf-one" });
    attempts++;
    if (attempts === 1) throw new TypeError("network down");
    return Response.json(session("recovered-access"));
  } });
  const runtime = new AuthRuntime(client);
  assert.equal((await runtime.restore()).status, "error");
  assert.deepEqual(await runtime.restore(), { status: "authenticated", user });
});
