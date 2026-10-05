import { useLoaderData, useParams } from "react-router";
import { DiscoveryPage } from "~/components/catalog/discovery-page";
import { loadScopedCatalog } from "~/features/catalog/scoped-listing.server";
import type { Route } from "./+types/brand";

export function meta({ data }: Route.MetaArgs) {
  const name = data?.taxonomy?.name;
  return [
    { title: name ? `${name} CCTV equipment | OctaCam` : "Brand equipment | OctaCam" },
    { name: "description", content: name ? `Browse published ${name} CCTV equipment with current PKR prices and availability.` : "Browse OctaCam CCTV brands." },
  ];
}

export function loader({ request, params }: Route.LoaderArgs) {
  return loadScopedCatalog(request, "brand", params.slug);
}

export default function Brand() {
  const { taxonomy, discovery } = useLoaderData<typeof loader>();
  const { slug } = useParams();
  return <DiscoveryPage
    data={discovery}
    heading={{
      eyebrow: "Browse by brand",
      title: taxonomy?.name ?? "Brand equipment",
      description: taxonomy?.description || "Published CCTV equipment in this brand.",
      breadcrumbs: [{ label: "Home", to: "/" }, { label: "All brands", to: "/brands" }, { label: taxonomy?.name ?? "Brand equipment" }],
    }}
    path={`/brands/${taxonomy?.slug ?? slug ?? ""}`}
    scope={{ brand: taxonomy?.slug ?? slug ?? "" }}
  />;
}
