import assert from "node:assert/strict";
import { test } from "node:test";
import { authFailure, authPageLink, authPayload, safeReturnTo, validateAuthValues } from "../app/features/auth/forms.ts";
import { ApiError } from "../app/lib/api/client.ts";

test("return navigation preserves local query/hash and rejects external, API and auth-loop destinations", () => {
  const local = "/cart?source=equipment#items";
  assert.equal(safeReturnTo(new URLSearchParams({ returnTo: local })), local);
  for (const path of ["https://evil.example", "//evil.example", "/\\evil.example", "/%2fevil.example", "/%252fevil.example", "/%5cevil.example", "/\n/evil", "/api/v1/auth/logout/", "/a/../login", "/register?returnTo=/cart", "/%6cogin", "not-a-path"]) {
    assert.equal(safeReturnTo(new URLSearchParams({ returnTo: path })), null, path);
  }
  assert.equal(safeReturnTo(new URLSearchParams("returnTo=/cart&returnTo=/shop")), null);
  assert.equal(authPageLink("register", local), "/register?returnTo=%2Fcart%3Fsource%3Dequipment%23items");
});

test("payload follows Django fields and preserves the password's literal whitespace", () => {
  const values = { full_name: " Buyer ", email: " buyer@example.com ", phone: " 03000000000 ", password: "  secret words  " };
  assert.deepEqual(authPayload(values, "login"), { email: "buyer@example.com", password: "  secret words  " });
  assert.deepEqual(authPayload(values, "register"), { email: "buyer@example.com", password: "  secret words  ", full_name: "Buyer", phone: "03000000000" });
  assert.deepEqual(values, { full_name: " Buyer ", email: " buyer@example.com ", phone: " 03000000000 ", password: "  secret words  " });
});

test("registration uses actual length limits without imposing registration password rules on sign-in", () => {
  const values = { full_name: "Buyer", email: "buyer@example.com", phone: "", password: "short" };
  assert.deepEqual(validateAuthValues(values, "login"), {});
  assert.deepEqual(validateAuthValues(values, "register"), { password: ["Use at least 8 characters."] });
  const errors = validateAuthValues({ ...values, full_name: "x".repeat(256), phone: "1".repeat(31), password: "long-enough" }, "register");
  assert.deepEqual(Object.keys(errors), ["full_name", "phone"]);
});

test("backend field errors survive and uncertain registration never claims success", () => {
  const fields = { email: ["An account with this email already exists."], password: ["This password is too common."] };
  const validation = authFailure(new ApiError({ status: 400, code: "VALIDATION_ERROR", message: "Some fields need attention.", fields }), "register");
  assert.deepEqual(validation.fields, fields);
  const uncertain = authFailure(new ApiError({ status: null, code: "NETWORK_ERROR", message: "Network unavailable" }), "register");
  assert.match(uncertain.message, /could not be confirmed/);
  assert.match(uncertain.message, /Try signing in/);
});
