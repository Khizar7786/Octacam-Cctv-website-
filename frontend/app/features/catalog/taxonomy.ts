import { apiPath, unexpectedApiResponse, type ApiClient, type ApiPath } from "../../lib/api/client.ts";
import { parsePaginatedResponse, type Paginated } from "../../lib/api/pagination.ts";

export interface PublicTaxonomy {
  id: number;
  name: string;
  slug: string;
  description: string;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface FilterOption {
  value: string;
  label: string;
}

export type SpecificationFilter =
  | { key: string; label: string; type: "choice"; unit: string | null; options: FilterOption[] }
  | { key: string; label: string; type: "boolean"; unit: string | null; options: { value: boolean; label: string }[] }
  | { key: string; label: string; type: "integer_range" | "decimal_range"; unit: string | null; min: string; max: string };

export interface DiscoveryFilterMetadata {
  brand: FilterOption[];
  category: FilterOption[];
  price: { min: string | null; max: string | null };
  specifications: SpecificationFilter[];
}

export type TaxonomyKind = "brands" | "categories";

const collectionPath = (kind: TaxonomyKind) => `/api/v1/catalog/${kind}/` as const;

export async function getPublicTaxonomies(
  client: ApiClient,
  kind: TaxonomyKind,
  options: { page?: number; signal?: AbortSignal } = {},
): Promise<Paginated<PublicTaxonomy>> {
  const path = apiPath(`${collectionPath(kind)}${options.page && options.page > 1 ? `?page=${options.page}` : ""}`);
  const body = await client.request<unknown>(path, { signal: options.signal });
  try {
    const page = parsePaginatedResponse(body, parseTaxonomy);
    for (const link of [page.next, page.previous]) {
      if (link && new URL(link, "http://octacam.invalid").pathname !== collectionPath(kind)) {
        throw new TypeError("Taxonomy pagination must stay in its collection.");
      }
    }
    return page;
  } catch (error) {
    if (error instanceof TypeError) throw unexpectedApiResponse(body);
    throw error;
  }
}

export async function getPublicTaxonomy(
  client: ApiClient,
  kind: TaxonomyKind,
  slug: string,
  signal?: AbortSignal,
): Promise<PublicTaxonomy> {
  const body = await client.request<unknown>(apiPath(`${collectionPath(kind)}${encodeURIComponent(slug)}/`), { signal });
  try {
    return parseTaxonomy(body);
  } catch (error) {
    if (error instanceof TypeError) throw unexpectedApiResponse(body);
    throw error;
  }
}

export async function getScopedFilterOptions(
  client: ApiClient,
  scope: { brand?: string; category?: string },
  signal?: AbortSignal,
): Promise<FilterOption[]> {
  const metadata = await getDiscoveryFilterMetadata(client, scope, signal);
  return scope.brand ? metadata.category : metadata.brand;
}

export async function getDiscoveryFilterMetadata(
  client: ApiClient,
  scope: { brand?: string; category?: string } = {},
  signal?: AbortSignal,
): Promise<DiscoveryFilterMetadata> {
  const query = new URLSearchParams(scope);
  const body = await client.request<unknown>(apiPath(`/api/v1/catalog/filters/${query.size ? `?${query}` : ""}`), { signal });
  try {
    const response = record(body);
    const price = record(response.price);
    return {
      brand: parseOptions(response.brand),
      category: parseOptions(response.category),
      price: {
        min: price.min === null ? null : string(price.min),
        max: price.max === null ? null : string(price.max),
      },
      specifications: parseSpecifications(response.specifications),
    };
  } catch (error) {
    if (error instanceof TypeError) throw unexpectedApiResponse(body);
    throw error;
  }
}

function parseOptions(options: unknown): FilterOption[] {
    if (!Array.isArray(options)) throw new TypeError("Filter options must be an array.");
    return options.map((option) => {
      const item = record(option);
      return { value: string(item.value), label: string(item.label) };
    });
}

function parseSpecifications(value: unknown): SpecificationFilter[] {
  if (!Array.isArray(value)) throw new TypeError("Specification filters must be an array.");
  return value.map((entry) => {
    const item = record(entry);
    const common = { key: string(item.key), label: string(item.label), unit: item.unit == null ? null : string(item.unit) };
    if (item.type === "choice") return { ...common, type: item.type, options: parseOptions(item.options) };
    if (item.type === "boolean") {
      if (!Array.isArray(item.options)) throw new TypeError("Boolean filter options must be an array.");
      const options = item.options.map((entry) => {
        const option = record(entry);
        if (typeof option.value !== "boolean") throw new TypeError("Boolean filter value must be a boolean.");
        return { value: option.value, label: string(option.label) };
      });
      return { ...common, type: item.type, options };
    }
    if (item.type === "integer_range" || item.type === "decimal_range") {
      return { ...common, type: item.type, min: string(item.min), max: string(item.max) };
    }
    throw new TypeError("Unsupported specification filter type.");
  });
}

export function scopedPageHref(link: ApiPath, routePath: string, facet?: { name: "brand" | "category"; value: string }): string {
  const page = new URL(link, "http://octacam.invalid").searchParams.get("page");
  const query = new URLSearchParams();
  if (facet) query.set(facet.name, facet.value);
  if (page && /^[1-9]\d*$/.test(page) && page !== "1") query.set("page", page);
  return `${routePath}${query.size ? `?${query}` : ""}`;
}

function parseTaxonomy(value: unknown): PublicTaxonomy {
  const item = record(value);
  if (!Number.isSafeInteger(item.id) || (item.id as number) < 1 || !Number.isSafeInteger(item.sort_order)) {
    throw new TypeError("Invalid taxonomy ID or sort order.");
  }
  if (item.is_active !== true) throw new TypeError("Public taxonomy must be active.");
  return {
    id: item.id as number,
    name: string(item.name),
    slug: string(item.slug),
    description: string(item.description),
    is_active: true,
    sort_order: item.sort_order as number,
    created_at: string(item.created_at),
    updated_at: string(item.updated_at),
  };
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError("Expected an object.");
  return value as Record<string, unknown>;
}

function string(value: unknown): string {
  if (typeof value !== "string") throw new TypeError("Expected a string.");
  return value;
}
