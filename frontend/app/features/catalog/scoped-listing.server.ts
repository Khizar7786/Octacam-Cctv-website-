import { data } from "react-router";
import { getPublicProducts } from "./api";
import { getPublicTaxonomy, getScopedFilterOptions, type PublicTaxonomy, type TaxonomyKind } from "./taxonomy";
import { ApiError } from "../../lib/api/client";
import { serverApiClient } from "../../lib/api/server-client.server";

type ScopeKind = "brand" | "category";

export function parseListingQuery(request: Request, facet?: ScopeKind) {
  const search = new URL(request.url).searchParams;
  const allowed = facet ? ["page", facet] : ["page"];
  if ([...search.keys()].some((key) => !allowed.includes(key) || search.getAll(key).length !== 1)) return null;
  const rawPage = search.get("page") ?? "1";
  if (!/^[1-9]\d*$/.test(rawPage)) return null;
  const pageNumber = Number(rawPage);
  if (!Number.isSafeInteger(pageNumber)) return null;
  const selected = facet ? search.get(facet) || null : null;
  if (selected !== null && !/^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(selected)) return null;
  return { pageNumber, selected };
}

export async function loadScopedCatalog(request: Request, kind: ScopeKind, slug: string | undefined) {
  if (!slug) throw data(null, { status: 404 });
  const mainKind: TaxonomyKind = kind === "brand" ? "brands" : "categories";
  const facetKind: TaxonomyKind = kind === "brand" ? "categories" : "brands";
  const facetName = kind === "brand" ? "category" : "brand";
  let taxonomy: PublicTaxonomy;
  try {
    taxonomy = await getPublicTaxonomy(serverApiClient, mainKind, slug, request.signal);
  } catch (error) {
    if (request.signal.aborted) throw error;
    if (error instanceof ApiError && error.status === 404) throw data(null, { status: 404 });
    return { state: "error" as const, taxonomy: null };
  }

  const query = parseListingQuery(request, facetName);
  if (!query) return { state: "invalid" as const, taxonomy };

  try {
    const selectedTaxonomy = query.selected
      ? await getPublicTaxonomy(serverApiClient, facetKind, query.selected, request.signal)
      : null;
    const scope = { [kind]: taxonomy.slug, ...(query.selected ? { [facetName]: query.selected } : {}) };
    const productQuery = new URLSearchParams(scope);
    if (query.pageNumber > 1) productQuery.set("page", String(query.pageNumber));
    const [catalog, options] = await Promise.all([
      getPublicProducts(serverApiClient, { searchParams: productQuery, signal: request.signal }),
      getScopedFilterOptions(serverApiClient, { [kind]: taxonomy.slug }, request.signal),
    ]);
    if (selectedTaxonomy && !options.some(({ value }) => value === selectedTaxonomy.slug)) {
      options.push({ value: selectedTaxonomy.slug, label: selectedTaxonomy.name });
    }
    return { state: "ready" as const, taxonomy, catalog, options, selected: query.selected, pageNumber: query.pageNumber };
  } catch (error) {
    if (request.signal.aborted) throw error;
    if (error instanceof ApiError && error.status === 404) return { state: "invalid" as const, taxonomy };
    return { state: "error" as const, taxonomy };
  }
}
