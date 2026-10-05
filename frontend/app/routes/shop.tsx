import { Link, useLoaderData, useNavigation, useRevalidator } from "react-router";
import { ProductCard } from "~/components/catalog/product-card";
import { getPublicProducts } from "~/features/catalog/api";
import { serverApiClient } from "~/lib/api/server-client.server";
import { ApiError, type ApiPath } from "~/lib/api/client";
import type { Route } from "./+types/shop";

export function meta() {
  return [
    { title: "Shop CCTV equipment | OctaCam" },
    { name: "description", content: "Browse published CCTV cameras, recorders, storage, and accessories with current PKR prices and availability." },
  ];
}

export async function loader({ request }: Route.LoaderArgs) {
  const search = new URL(request.url).searchParams;
  const pageValues = search.getAll("page");
  if ([...search.keys()].some((key) => key !== "page") || pageValues.length > 1) {
    return { state: "invalid" as const };
  }

  const pageNumber = pageValues.length === 0 ? 1 : Number(pageValues[0]);
  if (!Number.isSafeInteger(pageNumber) || pageNumber < 1 || !/^[1-9]\d*$/.test(pageValues[0] ?? "1")) {
    return { state: "invalid" as const };
  }

  try {
    const catalog = await getPublicProducts(serverApiClient, {
      searchParams: pageNumber === 1 ? undefined : new URLSearchParams({ page: String(pageNumber) }),
      signal: request.signal,
    });
    return { state: "ready" as const, catalog, pageNumber };
  } catch (error) {
    if (request.signal.aborted) throw error;
    if (error instanceof ApiError && error.status === 404) return { state: "invalid" as const };
    return { state: "error" as const };
  }
}

function shopPageHref(page: ApiPath): string {
  return `/shop${new URL(page, "http://octacam.invalid").search}`;
}

export default function Shop() {
  const data = useLoaderData<typeof loader>();
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  const loading = navigation.state === "loading" || revalidator.state === "loading";

  return (
    <div className="space-y-8">
      <div className="max-w-2xl">
        <p className="text-sm font-bold text-primary">OctaCam catalog</p>
        <h1 className="mt-2 text-[length:var(--font-size-heading)] font-bold leading-tight">Shop CCTV equipment</h1>
        <p className="mt-3 text-muted-foreground">Browse the published catalog. Prices and availability come from OctaCam&apos;s current product records; checkout is still being built.</p>
      </div>

      {revalidator.state === "loading" ? <p className="rounded-md border border-info bg-info-surface p-4 text-sm" role="status">Loading products...</p> : null}

      {data.state === "invalid" ? (
        <section className="rounded-lg border border-warning bg-warning-surface p-6">
          <h2 className="text-lg font-bold">This catalog page is unavailable</h2>
          <p className="mt-2 text-sm">The page address has an unsupported or invalid option.</p>
          <Link className="mt-3 inline-flex min-h-11 items-center" to="/shop">Browse from page 1</Link>
        </section>
      ) : null}

      {data.state === "error" ? (
        <section className="rounded-lg border border-error bg-error-surface p-6" role="alert">
          <h2 className="text-lg font-bold">Products could not be loaded</h2>
          <p className="mt-2 text-sm">Please try again. No product information is shown until the catalog responds.</p>
          <button className="mt-4 min-h-11 rounded-md border border-border-strong bg-card px-4 text-sm font-semibold hover:bg-accent disabled:opacity-60" disabled={loading} onClick={() => revalidator.revalidate()} type="button">Try again</button>
        </section>
      ) : null}

      {data.state === "ready" && data.catalog.count === 0 ? (
        <section className="rounded-lg border border-border bg-card p-6 sm:p-10">
          <h2 className="text-lg font-bold">No published products yet</h2>
          <p className="mt-2 text-sm text-muted-foreground">The catalog is empty right now. Return later to see equipment after it has been published.</p>
        </section>
      ) : null}

      {data.state === "ready" && data.catalog.count > 0 ? (
        <section aria-busy={loading} aria-labelledby="products-heading">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
            <h2 className="text-lg font-bold" id="products-heading">Published products</h2>
            <p className="text-sm text-muted-foreground">{data.catalog.count} products · Page {data.pageNumber}</p>
          </div>
          {data.catalog.results.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {data.catalog.results.map((product) => <ProductCard key={product.id} product={product} />)}
            </div>
          ) : (
            <p className="rounded-lg border border-border bg-card p-6">There are no products on this page. <Link to="/shop">Return to page 1</Link>.</p>
          )}
          {data.catalog.previous || data.catalog.next ? (
            <nav aria-label="Catalog pages" className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
              {data.catalog.previous ? (
                <Link className="inline-flex min-h-11 items-center rounded-md border border-border-strong bg-card px-4 text-sm no-underline hover:bg-accent" rel="prev" to={shopPageHref(data.catalog.previous)}>Previous page</Link>
              ) : <span />}
              {data.catalog.next ? (
                <Link className="inline-flex min-h-11 items-center rounded-md border border-border-strong bg-card px-4 text-sm no-underline hover:bg-accent" rel="next" to={shopPageHref(data.catalog.next)}>Next page</Link>
              ) : null}
            </nav>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
