import { data } from "react-router";
import { loadDiscovery } from "./discovery.server";
import { parseDiscoveryQuery } from "./discovery";
import { getPublicTaxonomy, type PublicTaxonomy, type TaxonomyKind } from "./taxonomy";
import { ApiError } from "../../lib/api/client";
import { serverApiClient } from "../../lib/api/server-client.server";

type ScopeKind = "brand" | "category";

export function parseListingQuery(request: Request) {
  const search = new URL(request.url).searchParams;
  if ([...search.keys()].some((key) => key !== "page" || search.getAll(key).length !== 1)) return null;
  const rawPage = search.get("page") ?? "1";
  if (!/^[1-9]\d*$/.test(rawPage)) return null;
  const pageNumber = Number(rawPage);
  return Number.isSafeInteger(pageNumber) ? { pageNumber } : null;
}

export async function loadScopedCatalog(request: Request, kind: ScopeKind, slug: string | undefined) {
  if (!slug) throw data(null, { status: 404 });
  const mainKind: TaxonomyKind = kind === "brand" ? "brands" : "categories";
  let taxonomy: PublicTaxonomy;
  try {
    taxonomy = await getPublicTaxonomy(serverApiClient, mainKind, slug, request.signal);
  } catch (error) {
    if (request.signal.aborted) throw error;
    if (error instanceof ApiError && error.status === 404) throw data(null, { status: 404 });
    const { query } = parseDiscoveryQuery(new URL(request.url).searchParams);
    Object.assign(query, { [kind]: slug });
    return { taxonomy: null, discovery: { state: "error" as const, query } };
  }
  const discovery = await loadDiscovery(request, { [kind]: taxonomy.slug });
  return { taxonomy, discovery };
}
