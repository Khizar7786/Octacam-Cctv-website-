import { ApiError, type ApiFieldErrors } from "../../lib/api/client.ts";

export type AuthMode = "login" | "register";
export type AuthField = "full_name" | "email" | "phone" | "password";
export interface AuthValues { full_name: string; email: string; phone: string; password: string }
export interface AuthFailure { message: string; fields: ApiFieldErrors }

export const emptyAuthValues: AuthValues = { full_name: "", email: "", phone: "", password: "" };

export function authFields(mode: AuthMode): AuthField[] {
  return mode === "register" ? ["full_name", "email", "phone", "password"] : ["email", "password"];
}

export function authPayload(values: AuthValues, mode: AuthMode) {
  const credentials = { email: values.email.trim(), password: values.password };
  return mode === "register"
    ? { ...credentials, full_name: values.full_name.trim(), phone: values.phone.trim() }
    : credentials;
}

export function validateAuthValues(values: AuthValues, mode: AuthMode): ApiFieldErrors {
  const fields: Record<string, string[]> = {};
  if (!values.email.trim()) fields.email = ["Enter your email address."];
  if (!values.password) fields.password = ["Enter your password."];
  if (mode === "register") {
    if (!values.full_name.trim()) fields.full_name = ["Enter your full name."];
    else if (values.full_name.trim().length > 255) fields.full_name = ["Use at most 255 characters."];
    if (values.phone.trim().length > 30) fields.phone = ["Use at most 30 characters."];
    if (values.password && values.password.length < 8) fields.password = ["Use at least 8 characters."];
  }
  return fields;
}

export function authFailure(error: unknown, mode: AuthMode): AuthFailure {
  if (error instanceof ApiError) {
    const uncertain = error.status === null || error.status >= 500 || error.code === "UNEXPECTED_API_RESPONSE";
    return {
      message: uncertain
        ? mode === "register"
          ? "Account creation could not be confirmed. Your inputs are still here. Try signing in before creating the account again."
          : "Sign-in could not be confirmed. Your inputs are still here. Please try again."
        : error.message,
      fields: error.fields,
    };
  }
  return { message: "The request could not be confirmed. Please try again.", fields: {} };
}

function unsafeCharacters(value: string, includeSpace = false): boolean {
  return Array.from(value).some((character) => character === "\\"
    || character.charCodeAt(0) < (includeSpace ? 33 : 32) || character.charCodeAt(0) === 127);
}

/** Allow a local page destination, excluding protocol tricks, API URLs, and auth loops. */
export function safeReturnTo(params: URLSearchParams): string | null {
  const values = params.getAll("returnTo");
  if (values.length !== 1) return null;
  const value = values[0];
  if (!value.startsWith("/") || value.startsWith("//") || unsafeCharacters(value)) return null;
  try {
    const url = new URL(value, "https://octacam.invalid");
    const path = decodeURIComponent(url.pathname);
    if (url.origin !== "https://octacam.invalid" || path.startsWith("//")
      || unsafeCharacters(path, true) || /%2f|%5c|%25/i.test(url.pathname)
      || /^\/(?:api|login|register)(?:\/|$)/i.test(path)) return null;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch { return null; }
}

export function authPageLink(mode: AuthMode, returnTo: string | null): string {
  return `/${mode}${returnTo ? `?${new URLSearchParams({ returnTo })}` : ""}`;
}
