import { Link } from "react-router";
import { getPublicProducts } from "../features/catalog/api.ts";
import { browserApiClient } from "../lib/api/browser-client.ts";
import { serverApiClient } from "../lib/api/server-client.server.ts";
import type { Route } from "./+types/foundation";

export function meta() {
  return [{ title: "Frontend foundation | OctaCam" }];
}

export async function loader({ request }: Route.LoaderArgs) {
  const products = await getPublicProducts(serverApiClient, { signal: request.signal });
  return { products, source: "server" as const };
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const products = await getPublicProducts(browserApiClient, { signal: request.signal });
  return { products, source: "browser" as const };
}

export default function Foundation({ loaderData }: Route.ComponentProps) {
  return (
    <section className="space-y-5">
      <h1 className="text-3xl font-semibold">Frontend foundation</h1>
      <p>
        {loaderData.source === "server"
          ? "The public catalog was loaded by the server API client during SSR."
          : "The public catalog was loaded by the browser API client through the same-origin proxy."}
      </p>
      <p role="status">
        {loaderData.products.count === 0
          ? "The live catalog currently has no published products."
          : `${loaderData.products.count} published products are available.`}
      </p>
      <p>This development page verifies the shared API boundary. The storefront will follow in later slices.</p>
      <p><Link to="/">Return home</Link></p>
    </section>
  );
}
