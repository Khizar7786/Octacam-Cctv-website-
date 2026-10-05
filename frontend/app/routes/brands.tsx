import { Link, useLoaderData, useNavigation, useRevalidator } from "react-router";
import { Breadcrumbs } from "~/components/catalog/catalog-listing";
import { buttonStyles } from "~/components/ui/button";
import { getPublicTaxonomies, scopedPageHref } from "~/features/catalog/taxonomy";
import { ApiError } from "~/lib/api/client";
import { serverApiClient } from "~/lib/api/server-client.server";
import { parseListingQuery } from "~/features/catalog/scoped-listing.server";
import type { Route } from "./+types/brands";

export function meta() {
  return [
    { title: "All CCTV brands | OctaCam" },
    { name: "description", content: "Browse active CCTV equipment brands in the OctaCam catalog." },
  ];
}

export async function loader({ request }: Route.LoaderArgs) {
  const query = parseListingQuery(request);
  if (!query) return { state: "invalid" as const };
  try {
    const brands = await getPublicTaxonomies(serverApiClient, "brands", { page: query.pageNumber, signal: request.signal });
    return { state: "ready" as const, brands, pageNumber: query.pageNumber };
  } catch (error) {
    if (request.signal.aborted) throw error;
    if (error instanceof ApiError && error.status === 404) return { state: "invalid" as const };
    return { state: "error" as const };
  }
}

export default function Brands() {
  const data = useLoaderData<typeof loader>();
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  const loading = navigation.state === "loading" || revalidator.state === "loading";

  return (
    <div className="space-y-8">
      <Breadcrumbs items={[{ label: "Home", to: "/" }, { label: "All brands" }]} />
      <header className="max-w-2xl">
        <p className="text-sm font-bold text-primary">OctaCam catalog</p>
        <h1 className="mt-2 text-[length:var(--font-size-heading)] font-bold leading-tight">All brands</h1>
        <p className="mt-3 text-muted-foreground">Explore active brands in the catalog. Products appear on each brand page when they have been published.</p>
      </header>
      {revalidator.state === "loading" ? <p className="rounded-md border border-info bg-info-surface p-4 text-sm" role="status">Loading brands...</p> : null}
      {data.state === "invalid" ? (
        <section className="rounded-lg border border-warning bg-warning-surface p-6">
          <h2 className="text-lg font-bold">This brand page is unavailable</h2>
          <p className="mt-2 text-sm">The page address has an invalid or unavailable option.</p>
          <Link className="mt-3 inline-flex min-h-11 items-center" to="/brands">Browse from page 1</Link>
        </section>
      ) : null}
      {data.state === "error" ? (
        <section className="rounded-lg border border-error bg-error-surface p-6" role="alert">
          <h2 className="text-lg font-bold">Brands could not be loaded</h2>
          <p className="mt-2 text-sm">Please try again.</p>
          <button className={buttonStyles({ variant: "outline", className: "mt-4" })} disabled={loading} onClick={() => revalidator.revalidate()} type="button">Try again</button>
        </section>
      ) : null}
      {data.state === "ready" ? (
        <section aria-busy={loading} aria-labelledby="brand-list-heading">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
            <h2 className="text-lg font-bold" id="brand-list-heading">Active brands</h2>
            <p className="text-sm text-muted-foreground">{data.brands.count} {data.brands.count === 1 ? "brand" : "brands"} · Page {data.pageNumber}</p>
          </div>
          {data.brands.count === 0 ? (
            <div className="rounded-lg border border-border bg-card p-6 sm:p-10">
              <h3 className="text-lg font-bold">No active brands yet</h3>
              <p className="mt-2 text-sm text-muted-foreground">Brand pages will appear here after they are made active.</p>
              <Link className="mt-3 inline-flex min-h-11 items-center" to="/shop">Browse published products</Link>
            </div>
          ) : data.brands.results.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {data.brands.results.map((brand) => (
                <Link className="flex min-h-32 flex-col justify-between gap-3 rounded-lg border border-border bg-card p-5 no-underline shadow-sm hover:border-primary" key={brand.id} to={`/brands/${brand.slug}`}>
                  <span className="text-xl font-bold text-foreground">{brand.name}</span>
                  {brand.description ? <span className="line-clamp-2 text-sm text-muted-foreground">{brand.description}</span> : null}
                  <span className="text-sm font-semibold text-primary">View brand</span>
                </Link>
              ))}
            </div>
          ) : <p className="rounded-lg border border-border bg-card p-6">There are no brands on this page. <Link to="/brands">Return to page 1</Link>.</p>}
          {data.brands.previous || data.brands.next ? (
            <nav aria-label="Brand pages" className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
              {data.brands.previous ? <Link className={buttonStyles({ variant: "outline" })} rel="prev" to={scopedPageHref(data.brands.previous, "/brands")}>Previous page</Link> : <span />}
              {data.brands.next ? <Link className={buttonStyles({ variant: "outline" })} rel="next" to={scopedPageHref(data.brands.next, "/brands")}>Next page</Link> : null}
            </nav>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
