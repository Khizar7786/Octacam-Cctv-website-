import { getPublicProductPage, getPublicProducts, type Paginated, type PublicProduct } from "../catalog/api.ts";
import type { ApiClient, ApiPath } from "../../lib/api/client.ts";

/** The public API has no ID lookup yet; walk its published collection using its pagination links. */
export async function resolveCartProducts(client: ApiClient, ids: readonly number[], signal?: AbortSignal): Promise<Map<number, PublicProduct>> {
  const pending = new Set(ids);
  const found = new Map<number, PublicProduct>();
  if (!pending.size) return found;
  const visited = new Set<string>();
  let next: ApiPath | null = "/api/v1/catalog/products/";
  while (next && pending.size) {
    if (visited.has(next)) throw new TypeError("The catalog returned a repeated pagination link.");
    visited.add(next);
    const page: Paginated<PublicProduct> = next === "/api/v1/catalog/products/"
      ? await getPublicProducts(client, { signal })
      : await getPublicProductPage(client, next, { signal });
    for (const product of page.results) {
      if (pending.delete(product.id)) found.set(product.id, product);
    }
    next = page.next;
  }
  return found;
}
