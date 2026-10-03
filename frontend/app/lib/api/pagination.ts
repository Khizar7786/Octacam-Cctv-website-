import { apiPath, type ApiPath } from "./client.ts";

export interface Paginated<T> {
  count: number;
  next: ApiPath | null;
  previous: ApiPath | null;
  results: T[];
}

export function parsePaginatedResponse<T>(
  value: unknown,
  parseResult: (value: unknown) => T,
): Paginated<T> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("The paginated response must be an object.");
  }
  const page = value as Record<string, unknown>;
  if (!Number.isInteger(page.count) || (page.count as number) < 0) {
    throw new TypeError("The paginated response count must be a non-negative integer.");
  }
  if (!Array.isArray(page.results)) {
    throw new TypeError("The paginated response results must be an array.");
  }

  return {
    count: page.count as number,
    next: normalizePageLink(page.next, "next"),
    previous: normalizePageLink(page.previous, "previous"),
    results: page.results.map(parseResult),
  };
}

function normalizePageLink(value: unknown, label: string): ApiPath | null {
  if (value === null) return null;
  if (typeof value !== "string") {
    throw new TypeError(`The paginated response ${label} link must be a string or null.`);
  }
  const parsed = new URL(value, "http://octacam.invalid");
  return apiPath(`${parsed.pathname}${parsed.search}`);
}
