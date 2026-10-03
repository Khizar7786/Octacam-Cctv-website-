import assert from "node:assert/strict";
import { test } from "node:test";
import { getRouteErrorContent } from "../app/lib/route-errors.ts";

test("missing routes have a useful recovery message without exposing thrown data", () => {
  const result = getRouteErrorContent({
    status: 404, statusText: "Not Found", internal: false,
    data: "private-reference-and-contact",
  });
  assert.equal(result.title, "Page not found");
  assert.match(result.message, /home page/);
  assert.doesNotMatch(JSON.stringify(result), /private-reference-and-contact/);
});

test("unexpected errors and thrown payloads never expose server details", () => {
  for (const error of [
    new Error("secret database connection and stack"),
    { status: 500, statusText: "Secret error", internal: false, data: "private address" },
    "unexpected secret", null, undefined,
  ]) {
    const result = getRouteErrorContent(error);
    assert.equal(result.title, "Unable to load this page");
    assert.match(result.message, /reload/);
    assert.doesNotMatch(JSON.stringify(result), /secret|private|database/i);
  }
});
