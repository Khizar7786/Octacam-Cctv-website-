import {
  apiPath,
  type ApiClient,
  type ApiPath,
  unexpectedApiResponse,
} from "../../lib/api/client.ts";
import { parsePaginatedResponse, type Paginated } from "../../lib/api/pagination.ts";

export type { Paginated } from "../../lib/api/pagination.ts";

declare const moneyBrand: unique symbol;
export type Money = string & { readonly [moneyBrand]: "Money" };

export interface TaxonomySummary {
  id: number;
  name: string;
  slug: string;
}

export interface ProductImage {
  id: number;
  image_url: string;
  alt_text: string;
  sort_order: number;
  width: number;
  height: number;
  created_at: string;
}

export interface PublicProduct {
  id: number;
  brand: TaxonomySummary;
  category: TaxonomySummary;
  sku: string;
  slug: string;
  name: string;
  short_description: string;
  regular_price: Money;
  sale_price: Money | null;
  selling_price: Money;
  stock_quantity: number;
  is_in_stock: boolean;
  primary_image: ProductImage | null;
}

const PRODUCTS_PATH = "/api/v1/catalog/products/" as const;
const MONEY_PATTERN = /^(?:0|[1-9]\d{0,9})\.\d{2}$/;

export async function getPublicProducts(
  client: ApiClient,
  options: { searchParams?: URLSearchParams; signal?: AbortSignal } = {},
): Promise<Paginated<PublicProduct>> {
  const query = options.searchParams?.toString();
  const path = apiPath(`${PRODUCTS_PATH}${query ? `?${query}` : ""}`);
  return requestProductPage(client, path, options.signal);
}

export async function getPublicProductPage(
  client: ApiClient,
  page: ApiPath,
  options: { signal?: AbortSignal } = {},
): Promise<Paginated<PublicProduct>> {
  const safePage = apiPath(page);
  assertProductPagePath(safePage);
  return requestProductPage(client, safePage, options.signal);
}

async function requestProductPage(
  client: ApiClient,
  path: ApiPath,
  signal?: AbortSignal,
): Promise<Paginated<PublicProduct>> {
  const body = await client.request<unknown>(path, { signal });
  try {
    return parseProductPage(body);
  } catch (error) {
    if (error instanceof TypeError) throw unexpectedApiResponse(body);
    throw error;
  }
}

function parseProductPage(value: unknown): Paginated<PublicProduct> {
  const page = parsePaginatedResponse(value, parseProduct);
  if (page.next) assertProductPagePath(page.next);
  if (page.previous) assertProductPagePath(page.previous);
  return page;
}

function assertProductPagePath(path: ApiPath): void {
  const parsed = new URL(path, "http://octacam.invalid");
  if (parsed.pathname !== PRODUCTS_PATH) {
    throw new TypeError("A product pagination link must target the public product collection.");
  }
}

function parseProduct(value: unknown): PublicProduct {
  const product = expectRecord(value, "product");
  return {
    id: expectPositiveInteger(product.id, "product.id"),
    brand: parseTaxonomy(product.brand, "product.brand"),
    category: parseTaxonomy(product.category, "product.category"),
    sku: expectString(product.sku, "product.sku"),
    slug: expectString(product.slug, "product.slug"),
    name: expectString(product.name, "product.name"),
    short_description: expectString(product.short_description, "product.short_description"),
    regular_price: parseMoney(product.regular_price, "product.regular_price"),
    sale_price: product.sale_price === null ? null : parseMoney(product.sale_price, "product.sale_price"),
    selling_price: parseMoney(product.selling_price, "product.selling_price"),
    stock_quantity: expectNonNegativeInteger(product.stock_quantity, "product.stock_quantity"),
    is_in_stock: expectBoolean(product.is_in_stock, "product.is_in_stock"),
    primary_image: product.primary_image === null
      ? null
      : parseImage(product.primary_image, "product.primary_image"),
  };
}

function parseTaxonomy(value: unknown, label: string): TaxonomySummary {
  const taxonomy = expectRecord(value, label);
  return {
    id: expectPositiveInteger(taxonomy.id, `${label}.id`),
    name: expectString(taxonomy.name, `${label}.name`),
    slug: expectString(taxonomy.slug, `${label}.slug`),
  };
}

function parseImage(value: unknown, label: string): ProductImage {
  const image = expectRecord(value, label);
  return {
    id: expectPositiveInteger(image.id, `${label}.id`),
    image_url: expectString(image.image_url, `${label}.image_url`),
    alt_text: expectString(image.alt_text, `${label}.alt_text`),
    sort_order: expectNonNegativeInteger(image.sort_order, `${label}.sort_order`),
    width: expectPositiveInteger(image.width, `${label}.width`),
    height: expectPositiveInteger(image.height, `${label}.height`),
    created_at: expectString(image.created_at, `${label}.created_at`),
  };
}

function parseMoney(value: unknown, label: string): Money {
  const money = expectString(value, label);
  if (!MONEY_PATTERN.test(money)) throw new TypeError(`${label} must be a two-place decimal string.`);
  return money as Money;
}

function expectRecord(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`${label} must be an object.`);
  }
  return value as Record<string, unknown>;
}

function expectString(value: unknown, label: string): string {
  if (typeof value !== "string") throw new TypeError(`${label} must be a string.`);
  return value;
}

function expectBoolean(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") throw new TypeError(`${label} must be a boolean.`);
  return value;
}

function expectPositiveInteger(value: unknown, label: string): number {
  if (!Number.isInteger(value) || (value as number) <= 0) throw new TypeError(`${label} must be a positive integer.`);
  return value as number;
}

function expectNonNegativeInteger(value: unknown, label: string): number {
  if (!Number.isInteger(value) || (value as number) < 0) throw new TypeError(`${label} must be a non-negative integer.`);
  return value as number;
}
