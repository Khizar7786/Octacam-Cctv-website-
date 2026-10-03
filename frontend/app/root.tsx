import type { ReactNode } from "react";
import {
  Link,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "react-router";
import type { Route } from "./+types/root";
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
        <div className="mx-auto w-full max-w-2xl px-5 py-10 sm:py-16">
          <header className="mb-10">
            <Link className="font-semibold" to="/">OctaCam</Link>
          </header>
          <main id="main-content" tabIndex={-1}>{children}</main>
        </div>
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
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
