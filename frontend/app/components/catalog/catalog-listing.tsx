import { Link, useNavigation, useRevalidator } from "react-router";
import { ProductCard } from "./product-card";
import { scopedPageHref, type FilterOption, type PublicTaxonomy } from "~/features/catalog/taxonomy";
import type { Paginated, PublicProduct } from "~/features/catalog/api";
import { buttonStyles } from "~/components/ui/button";

type ListingData =
  | { state: "ready"; taxonomy: PublicTaxonomy; catalog: Paginated<PublicProduct>; options: FilterOption[]; selected: string | null; pageNumber: number }
  | { state: "invalid"; taxonomy: PublicTaxonomy }
  | { state: "error"; taxonomy: PublicTaxonomy | null };

export function Breadcrumbs({ items }: { items: { label: string; to?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {items.map((item, index) => (
          <li className="flex items-center gap-2" key={`${item.label}-${index}`}>
            {index ? <span aria-hidden="true">/</span> : null}
            {item.to ? <Link to={item.to}>{item.label}</Link> : <span aria-current="page">{item.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function CatalogListing({ data, kind }: { data: ListingData; kind: "brand" | "category" }) {
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  const loading = navigation.state === "loading" || revalidator.state === "loading";
  const taxonomy = data.taxonomy;
  const path = taxonomy ? `/${kind === "brand" ? "brands" : "categories"}/${taxonomy.slug}` : "/shop";
  const title = taxonomy?.name ?? "Catalog";
  const facetName = kind === "brand" ? "category" : "brand";
  const facetLabel = kind === "brand" ? "Category" : "Brand";
  const parent = kind === "brand" ? { label: "All brands", to: "/brands" } : { label: "Shop", to: "/shop" };

  return (
    <div className="space-y-8">
      <Breadcrumbs items={[{ label: "Home", to: "/" }, parent, { label: title }]} />
      <header className="max-w-3xl">
        <p className="text-sm font-bold text-primary">Browse by {kind}</p>
        <h1 className="mt-2 text-[length:var(--font-size-heading)] font-bold leading-tight">{title}</h1>
        {taxonomy?.description ? <p className="mt-3 text-muted-foreground">{taxonomy.description}</p> : (
          <p className="mt-3 text-muted-foreground">Published CCTV equipment in this {kind}.</p>
        )}
      </header>

      {revalidator.state === "loading" ? <p className="rounded-md border border-info bg-info-surface p-4 text-sm" role="status">Loading products...</p> : null}

      {data.state === "invalid" ? (
        <section className="rounded-lg border border-warning bg-warning-surface p-6">
          <h2 className="text-lg font-bold">This catalog selection is unavailable</h2>
          <p className="mt-2 text-sm">The page address or selected {facetName} is invalid or unavailable.</p>
          <Link className="mt-3 inline-flex min-h-11 items-center" to={path}>Browse all {title} products</Link>
        </section>
      ) : null}

      {data.state === "error" ? (
        <section className="rounded-lg border border-error bg-error-surface p-6" role="alert">
          <h2 className="text-lg font-bold">Catalog information could not be loaded</h2>
          <p className="mt-2 text-sm">Please try again before browsing products.</p>
          <button className={buttonStyles({ variant: "outline", className: "mt-4" })} disabled={loading} onClick={() => revalidator.revalidate()} type="button">Try again</button>
        </section>
      ) : null}

      {data.state === "ready" ? (
        <>
          <form action={path} className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-4" method="get">
            <div className="min-w-48 flex-1 sm:max-w-xs">
              <label className="mb-1 block text-sm font-semibold" htmlFor={`${kind}-facet`}>{facetLabel}</label>
              <select className="min-h-11 w-full rounded-md border border-input bg-background px-3 text-foreground" defaultValue={data.selected ?? ""} id={`${kind}-facet`} key={data.selected ?? "all"} name={facetName}>
                <option value="">All {facetLabel.toLowerCase()}s</option>
                {data.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
            <button className={buttonStyles()} type="submit">Show products</button>
          </form>

          <section aria-busy={loading} aria-labelledby="products-heading">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
              <h2 className="text-lg font-bold" id="products-heading">Published products</h2>
              <p className="text-sm text-muted-foreground">{data.catalog.count} {data.catalog.count === 1 ? "product" : "products"} · Page {data.pageNumber}</p>
            </div>
            {data.catalog.count === 0 ? (
              <div className="rounded-lg border border-border bg-card p-6 sm:p-10">
                <h3 className="text-lg font-bold">No published products in this selection</h3>
                <p className="mt-2 text-sm text-muted-foreground">Try another {facetName} or browse the full catalog.</p>
                <Link className="mt-3 inline-flex min-h-11 items-center" to="/shop">Browse all products</Link>
              </div>
            ) : data.catalog.results.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {data.catalog.results.map((product) => <ProductCard key={product.id} product={product} />)}
              </div>
            ) : (
              <p className="rounded-lg border border-border bg-card p-6">There are no products on this page. <Link to={path}>Return to page 1</Link>.</p>
            )}
            {data.catalog.previous || data.catalog.next ? (
              <nav aria-label="Catalog pages" className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
                {data.catalog.previous ? <Link className={buttonStyles({ variant: "outline" })} rel="prev" to={scopedPageHref(data.catalog.previous, path, data.selected ? { name: facetName, value: data.selected } : undefined)}>Previous page</Link> : <span />}
                {data.catalog.next ? <Link className={buttonStyles({ variant: "outline" })} rel="next" to={scopedPageHref(data.catalog.next, path, data.selected ? { name: facetName, value: data.selected } : undefined)}>Next page</Link> : null}
              </nav>
            ) : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
