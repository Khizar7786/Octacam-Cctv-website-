import { useLoaderData, useParams } from "react-router";
import { DiscoveryPage } from "~/components/catalog/discovery-page";
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
  const { taxonomy, discovery } = useLoaderData<typeof loader>();
  const { slug } = useParams();
  return <DiscoveryPage
    data={discovery}
    heading={{
      eyebrow: "Browse by category",
      title: taxonomy?.name ?? "CCTV category",
      description: taxonomy?.description || "Published CCTV equipment in this category.",
      breadcrumbs: [{ label: "Home", to: "/" }, { label: "Shop", to: "/shop" }, { label: taxonomy?.name ?? "CCTV category" }],
    }}
    path={`/categories/${taxonomy?.slug ?? slug ?? ""}`}
    scope={{ category: taxonomy?.slug ?? slug ?? "" }}
  />;
}
