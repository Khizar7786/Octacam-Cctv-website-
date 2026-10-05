import { useEffect, useRef, type ReactNode } from "react";
import {
  Link,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useLocation,
  useNavigation,
} from "react-router";
import type { Route } from "./+types/root";
import { Container } from "./components/layout/container";
import { SiteFooter } from "./components/layout/site-footer";
import { SiteHeader } from "./components/layout/site-header";
import { getRouteErrorContent } from "./lib/route-errors";
import { brandLinks, categoryLinks } from "./config/storefront";
import { getPublicTaxonomies, getPublicTaxonomy } from "./features/catalog/taxonomy";
import { serverApiClient } from "./lib/api/server-client.server";
import "./styles/app.css";

export function headers() {
  return {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
  };
}

export async function loader({ request }: Route.LoaderArgs) {
  const [brands, categories] = await Promise.all([
    getPublicTaxonomies(serverApiClient, "brands", { signal: request.signal }).catch((error: unknown) => {
      if (request.signal.aborted) throw error;
      return null;
    }),
    getPublicTaxonomies(serverApiClient, "categories", { signal: request.signal }).catch((error: unknown) => {
      if (request.signal.aborted) throw error;
      return null;
    }),
  ]);
  const activeBrandSlugs = new Set(brands?.results.map((brand) => brand.slug) ?? []);
  const activeCategorySlugs = new Set(categories?.results.map((category) => category.slug) ?? []);
  const missingFeatured = [
    ...(brands && brands.count > brands.results.length ? brandLinks.filter((link) => link.to !== "/brands" && !activeBrandSlugs.has(link.to.split("/").at(-1) ?? "")).map((link) => ({ kind: "brands" as const, slug: link.to.split("/").at(-1) ?? "" })) : []),
    ...(categories && categories.count > categories.results.length ? categoryLinks.filter((link) => !activeCategorySlugs.has(link.to.split("/").at(-1) ?? "")).map((link) => ({ kind: "categories" as const, slug: link.to.split("/").at(-1) ?? "" })) : []),
  ];
  await Promise.all(missingFeatured.map(async ({ kind, slug }) => {
    try {
      await getPublicTaxonomy(serverApiClient, kind, slug, request.signal);
      (kind === "brands" ? activeBrandSlugs : activeCategorySlugs).add(slug);
    } catch (error) {
      if (request.signal.aborted) throw error;
      // Missing and inactive taxonomies are not promoted in navigation.
    }
  }));
  return {
    brandsUnavailable: brands === null,
    categoriesUnavailable: categories === null,
    brandLinks: brandLinks.filter((link) => link.to === "/brands" || activeBrandSlugs.has(link.to.split("/").at(-1) ?? "")),
    categoryLinks: categoryLinks.filter((link) => activeCategorySlugs.has(link.to.split("/").at(-1) ?? "")),
  };
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="robots" content="noindex, nofollow" />
        <Meta />
        <Links />
      </head>
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <SiteHeader />
        <Container className="min-h-[45vh] py-8 sm:py-12">
          <main id="main-content" tabIndex={-1}>{children}</main>
        </Container>
        <SiteFooter />
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  const navigation = useNavigation();
  const location = useLocation();
  const previousPath = useRef(location.pathname);

  useEffect(() => {
    if (previousPath.current === location.pathname) return;
    previousPath.current = location.pathname;
    document.getElementById("main-content")?.focus();
  }, [location.pathname]);

  return (
    <>
      {navigation.state === "loading" ? (
        <p className="mb-5 border-l-4 border-info bg-info-surface px-4 py-3 text-sm" role="status">
          Loading page...
        </p>
      ) : null}
      <Outlet />
    </>
  );
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  const { title, message } = getRouteErrorContent(error);

  return (
    <section aria-labelledby="error-heading" className="space-y-5">
      <title>{`${title} | OctaCam`}</title>
      <h1 id="error-heading" className="text-3xl font-semibold">{title}</h1>
      <p>{message}</p>
      <p><Link to="/">Return home</Link></p>
    </section>
  );
}
