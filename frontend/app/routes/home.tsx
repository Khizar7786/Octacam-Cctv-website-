import type { ReactNode } from "react";
import { Link, useLoaderData, useRouteLoaderData } from "react-router";
import { ProductCard } from "~/components/catalog/product-card";
import { PromoCarousel } from "~/components/home/promo-carousel";
import { BrandStrip } from "~/components/home/brand-strip";
import { ReassuranceStrip } from "~/components/home/reassurance-strip";
import { getPublicProducts, type PublicProduct } from "~/features/catalog/api";
import { serverApiClient } from "~/lib/api/server-client.server";
import type { loader as rootLoader } from "../root";
import type { Route } from "./+types/home";

export function meta() {
  return [
    { title: "CCTV equipment and Lahore site surveys | OctaCam" },
    { name: "description", content: "Explore CCTV cameras, recorders, storage, and accessories. OctaCam also offers free site surveys in Lahore; installation is quoted afterward." },
  ];
}

export async function loader({ request }: Route.LoaderArgs) {
  try {
    const page = await getPublicProducts(serverApiClient, { signal: request.signal });
    return { products: page.results.slice(0, 5), catalogUnavailable: false };
  } catch (error) {
    if (request.signal.aborted) throw error;
    return { products: [] as PublicProduct[], catalogUnavailable: true };
  }
}

function SectionHeading({ eyebrow, title, id, children }: { eyebrow: string; title: string; id: string; children?: ReactNode }) {
  return (
    <div className="mb-4 max-w-2xl">
      <p className="text-sm font-bold text-primary">{eyebrow}</p>
      <h2 className="mt-2 text-[length:var(--font-size-heading)] font-bold leading-tight tracking-tight" id={id}>{title}</h2>
      {children ? <p className="mt-2 text-muted-foreground">{children}</p> : null}
    </div>
  );
}

export default function Home() {
  const { products, catalogUnavailable } = useLoaderData<typeof loader>();
  const active = useRouteLoaderData<typeof rootLoader>("root");
  const visibleCategoryLinks = active?.categoryLinks ?? [];

  return (
    <div className="space-y-8 sm:space-y-10">
      <PromoCarousel />

      <ReassuranceStrip />

      {products.length > 0 ? (
        <section aria-labelledby="products-heading" id="published-products">
          <SectionHeading eyebrow="From the catalog" id="products-heading" title="Published equipment">Explore current products, prices, and specifications.</SectionHeading>
          <div className="product-grid">
            {products.map((product) => <ProductCard key={product.id} product={product} />)}
          </div>
        </section>
      ) : null}

      {catalogUnavailable ? (
        <p className="rounded-md border border-warning bg-warning-surface p-4 text-sm" role="status">
          The product catalog is unavailable right now. Please try again later.
        </p>
      ) : null}

      <BrandStrip brands={active?.brandEntries ?? []} unavailable={active?.brandsUnavailable ?? false} />

      <section aria-labelledby="categories-heading" id="categories">
        <SectionHeading eyebrow="Shop by category" id="categories-heading" title="Find the right type of equipment" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {visibleCategoryLinks.map(({ label, to }) => (
            <Link className="flex min-h-28 flex-col justify-between rounded-lg border border-border bg-card p-5 no-underline shadow-sm hover:border-primary" key={to} to={to}>
              <span className="text-xl font-bold text-foreground">{label === "Recorders" ? "DVR/NVR recorders" : label === "Storage" ? "Surveillance storage" : label}</span>
              <span className="text-xs font-semibold text-primary">Browse products</span>
            </Link>
          ))}
        </div>
        {visibleCategoryLinks.length === 0 ? <p className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground" role="status">{active?.categoriesUnavailable ? "Equipment categories are unavailable right now." : "No active equipment categories are available yet."}</p> : null}
        <Link className="mt-5 inline-flex min-h-11 items-center text-sm" to="/shop">Browse all published products</Link>
      </section>

      <section aria-labelledby="survey-heading" className="rounded-lg border border-border bg-accent p-5 sm:p-8" id="lahore-survey">
        <p className="text-sm font-bold text-primary">Free Lahore site survey</p>
        <h2 className="mt-2 text-[length:var(--font-size-heading)] font-bold leading-tight" id="survey-heading">Need help planning your system?</h2>
        <p className="mt-3 max-w-2xl text-muted-foreground">A Lahore customer can request a free site survey without buying equipment. Installation is discussed, quoted, and scheduled separately after the survey.</p>
        <Link className="mt-6 inline-flex min-h-11 items-center rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground no-underline hover:bg-primary-hover hover:text-primary-foreground" to="/surveys">
          Survey booking <span className="ml-2 text-xs">(coming soon)</span>
        </Link>
      </section>
    </div>
  );
}
