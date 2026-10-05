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
import "./styles/app.css";

export function headers() {
  return {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
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
