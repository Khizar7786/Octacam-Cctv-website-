import type { ApiPath } from "../../lib/api/client.ts";
import type { SpecificationFilter } from "./taxonomy.ts";

export type Availability = "" | "in_stock" | "out_of_stock";
export type ProductSort = "relevance" | "price_asc" | "price_desc";

export interface DiscoveryQuery {
  q: string;
  brand: string;
  category: string;
  min_price: string;
  max_price: string;
  availability: Availability;
  sort: ProductSort;
  page: number;
  specifications: Record<string, string>;
}

export type DiscoveryScope = Partial<Pick<DiscoveryQuery, "brand" | "category">>;

export type DiscoveryField = keyof Omit<DiscoveryQuery, "page" | "specifications">;
export type DiscoveryErrors = Record<string, string | undefined>;

const fields = ["q", "brand", "category", "min_price", "max_price", "availability", "sort", "page"] as const;
const pricePattern = /^\d{1,10}(?:\.\d{1,2})?$/;
const slugPattern = /^[a-zA-Z0-9_-]{1,120}$/;
const specificationParameterPattern = /^spec_[a-zA-Z0-9_-]+$/;
const integerPattern = /^-?\d+$/;
const decimalPattern = /^-?\d{1,14}(?:\.\d{1,4})?$/;

export function parseDiscoveryQuery(search: URLSearchParams): { query: DiscoveryQuery; errors: DiscoveryErrors } {
  const errors: DiscoveryErrors = {};
  for (const key of search.keys()) {
    if ((!fields.includes(key as typeof fields[number]) && !specificationParameterPattern.test(key)) || search.getAll(key).length !== 1) {
      errors.url = "The address contains an unsupported or repeated option.";
    }
  }
  const specifications: Record<string, string> = {};
  for (const [key, value] of search) {
    if (specificationParameterPattern.test(key)) specifications[key] = value;
  }
  const query: DiscoveryQuery = {
    q: (search.get("q") ?? "").trim(),
    brand: search.get("brand") ?? "",
    category: search.get("category") ?? "",
    min_price: search.get("min_price") ?? "",
    max_price: search.get("max_price") ?? "",
    availability: (search.get("availability") ?? "") as Availability,
    sort: (search.get("sort") ?? "relevance") as ProductSort,
    page: Number(search.get("page") ?? "1"),
    specifications,
  };
  if (query.q.length > 120) errors.q = "Search must be 120 characters or fewer.";
  for (const key of ["brand", "category"] as const) {
    if (query[key] && !slugPattern.test(query[key])) errors[key] = `Select a valid ${key}.`;
  }
  for (const key of ["min_price", "max_price"] as const) {
    if (query[key] && !pricePattern.test(query[key])) errors[key] = "Enter a PKR amount with up to two decimal places.";
  }
  if (!errors.min_price && !errors.max_price && query.min_price && query.max_price && cents(query.min_price) > cents(query.max_price)) {
    errors.max_price = "Maximum price must be at least minimum price.";
  }
  if (!(["", "in_stock", "out_of_stock"] as string[]).includes(query.availability)) errors.availability = "Select a valid availability.";
  if (!(["relevance", "price_asc", "price_desc"] as string[]).includes(query.sort)) errors.sort = "Select a valid sort order.";
  if (!/^[1-9]\d*$/.test(search.get("page") ?? "1") || !Number.isSafeInteger(query.page)) errors.page = "Select a valid page number.";
  if (Object.keys(specifications).length && !query.category) errors.category = "Select a category to use technical filters.";
  return { query, errors };
}

export function validateTechnicalFilters(query: DiscoveryQuery, definitions: SpecificationFilter[]): DiscoveryErrors {
  const errors: DiscoveryErrors = {};
  const allowed = new Map<string, SpecificationFilter>();
  for (const definition of definitions) {
    if (definition.type === "choice" || definition.type === "boolean") allowed.set(`spec_${definition.key}`, definition);
  }
  for (const definition of definitions) {
    if (definition.type !== "integer_range" && definition.type !== "decimal_range") continue;
    for (const suffix of ["min", "max"] as const) {
      const parameter = `spec_${definition.key}_${suffix}`;
      if (!allowed.has(parameter)) allowed.set(parameter, definition);
    }
  }
  for (const [parameter, value] of Object.entries(query.specifications)) {
    const exact = definitions.find((item) => parameter === `spec_${item.key}`);
    if (exact?.type === "integer_range" || exact?.type === "decimal_range") {
      errors[parameter] = "Use minimum or maximum for this numeric filter.";
      continue;
    }
    const definition = allowed.get(parameter);
    // Metadata contains observed values only; Django decides whether an unobserved
    // choice or definition is still active and should produce an empty result.
    if (definition?.type === "choice") {
      if (!value) errors[parameter] = "Select a value.";
    } else if (definition?.type === "boolean") {
      if (value !== "true" && value !== "false") errors[parameter] = "Use Yes or No.";
    } else if (definition && !(definition.type === "integer_range" ? integerPattern : decimalPattern).test(value)) {
      errors[parameter] = definition.type === "integer_range" ? "Enter a whole number." : "Enter a number with up to four decimal places.";
    }
  }
  for (const definition of definitions) {
    if (definition.type !== "integer_range" && definition.type !== "decimal_range") continue;
    const minKey = `spec_${definition.key}_min`;
    const maxKey = `spec_${definition.key}_max`;
    if (allowed.get(minKey) !== definition || allowed.get(maxKey) !== definition) continue;
    const min = query.specifications[minKey];
    const max = query.specifications[maxKey];
    if (min && max && !errors[minKey] && !errors[maxKey] && scaledNumber(min) > scaledNumber(max)) {
      errors[maxKey] = "Maximum must be at least minimum.";
    }
  }
  return errors;
}

export function discoverySearchParams(query: DiscoveryQuery, scope: DiscoveryScope = {}): URLSearchParams {
  const search = new URLSearchParams();
  for (const key of ["q", "brand", "category", "min_price", "max_price", "availability"] as const) {
    if (query[key] && !(key in scope)) search.set(key, query[key]);
  }
  for (const key of Object.keys(query.specifications).sort()) search.set(key, query.specifications[key]);
  if (query.sort !== "relevance") search.set("sort", query.sort);
  if (query.page > 1) search.set("page", String(query.page));
  return search;
}

export function discoveryHref(path: string, query: DiscoveryQuery, scope: DiscoveryScope = {}): string {
  const search = discoverySearchParams(query, scope).toString();
  return `${path}${search ? `?${search}` : ""}`;
}

export function discoveryPageHref(path: string, query: DiscoveryQuery, pageLink: ApiPath, scope: DiscoveryScope = {}): string {
  const nextPage = new URL(pageLink, "http://octacam.invalid").searchParams.get("page") ?? "1";
  if (!/^[1-9]\d*$/.test(nextPage) || !Number.isSafeInteger(Number(nextPage))) {
    throw new TypeError("The product page link must contain a valid page number.");
  }
  return discoveryHref(path, { ...query, page: Number(nextPage) }, scope);
}

export function withoutFilters(query: DiscoveryQuery, scope: DiscoveryScope = {}): DiscoveryQuery {
  return { ...query, brand: scope.brand ?? "", category: scope.category ?? "", min_price: "", max_price: "", availability: "", specifications: {}, page: 1 };
}

export function withCategory(query: DiscoveryQuery, category: string, scope: DiscoveryScope = {}): DiscoveryQuery {
  if (category === query.category) return query;
  return { ...query, category, brand: scope.brand ?? "", specifications: {}, page: 1 };
}

function cents(value: string): bigint {
  const [whole, fraction = ""] = value.split(".");
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
}

function scaledNumber(value: string): bigint {
  const negative = value.startsWith("-");
  const [whole, fraction = ""] = (negative ? value.slice(1) : value).split(".");
  const amount = BigInt(whole) * 10000n + BigInt(fraction.padEnd(4, "0"));
  return negative ? -amount : amount;
}
