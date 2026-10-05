import { useLoaderData } from "react-router";
import { CatalogListing } from "~/components/catalog/catalog-listing";
import { loadScopedCatalog } from "~/features/catalog/scoped-listing.server";
import type { Route } from "./+types/category";

export function meta({ data }: Route.MetaArgs) {
  const name = data?.taxonomy?.name;
  return [
    { title: name ? `${name} | OctaCam CCTV equipment` : "CCTV category | OctaCam" },
    { name: "description", content: name ? `Browse published ${name} with current PKR prices and availability.` : "Browse OctaCam CCTV categories." },
  ];
}

export function loader({ request, params }: Route.LoaderArgs) {
  return loadScopedCatalog(request, "category", params.slug);
}

export default function Category() {
  return <CatalogListing data={useLoaderData<typeof loader>()} kind="category" />;
}
