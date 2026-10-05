import { getPublicProducts } from "./api";
import { parseDiscoveryQuery, discoverySearchParams, validateTechnicalFilters, type DiscoveryErrors, type DiscoveryScope } from "./discovery";
import { getDiscoveryFilterMetadata, getPublicTaxonomy } from "./taxonomy";
import { ApiError } from "../../lib/api/client";
import { serverApiClient } from "../../lib/api/server-client.server";

export async function loadDiscovery(request: Request, scope: DiscoveryScope = {}) {
  const requestSearch = new URL(request.url).searchParams;
  const { query, errors } = parseDiscoveryQuery(requestSearch);
  if ((scope.brand && requestSearch.has("brand")) || (scope.category && requestSearch.has("category"))) {
    errors.url = "The page address contains a filter that conflicts with this catalog page.";
  }
  Object.assign(query, scope);
  if (scope.category && errors.category === "Select a category to use technical filters.") delete errors.category;
  if (Object.keys(errors).length) return { state: "invalid" as const, query, errors };

  try {
    const [filters, scopedFilters] = await Promise.all([
      getDiscoveryFilterMetadata(serverApiClient, {}, request.signal),
      query.category ? getDiscoveryFilterMetadata(serverApiClient, { category: query.category }, request.signal) : Promise.resolve(null),
    ]);
    filters.specifications = scopedFilters?.specifications ?? [];
    for (const [field, kind] of [["brand", "brands"], ["category", "categories"]] as const) {
      const slug = query[field];
      if (slug && !filters[field].some((option) => option.value === slug)) {
        let taxonomy;
        try {
          taxonomy = await getPublicTaxonomy(serverApiClient, kind, slug, request.signal);
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) {
            return { state: "invalid" as const, query, errors: { [field]: `This ${field} is unavailable.` } as DiscoveryErrors };
          }
          throw error;
        }
        filters[field].push({ value: taxonomy.slug, label: taxonomy.name });
      }
    }
    const technicalErrors = validateTechnicalFilters(query, filters.specifications);
    if (Object.keys(technicalErrors).length) return { state: "invalid" as const, query, errors: technicalErrors, filters };
    let catalog;
    try {
      catalog = await getPublicProducts(serverApiClient, { searchParams: discoverySearchParams(query), signal: request.signal });
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        const fieldErrors = Object.fromEntries(Object.entries(error.fields).map(([field, messages]) => [field, messages[0]]));
        return { state: "invalid" as const, query, errors: Object.keys(fieldErrors).length ? fieldErrors : { url: "Review the selected catalog filters." }, filters };
      }
      throw error;
    }
    return { state: "ready" as const, query, catalog, filters };
  } catch (error) {
    if (request.signal.aborted) throw error;
    if (error instanceof ApiError && error.status === 404) {
      const queryErrors: DiscoveryErrors = { page: "This page or selected filter is unavailable." };
      return { state: "invalid" as const, query, errors: queryErrors };
    }
    if (error instanceof ApiError && error.status === 400) {
      const queryErrors: DiscoveryErrors = { url: "The catalog could not use these options. Review the filters and try again." };
      return { state: "invalid" as const, query, errors: queryErrors };
    }
    return { state: "error" as const, query };
  }
}
