import { useLoaderData } from "react-router";
import { DiscoveryPage } from "~/components/catalog/discovery-page";
import { loadDiscovery } from "~/features/catalog/discovery.server";
import type { Route } from "./+types/search";

export function meta({ data }: Route.MetaArgs) {
  const query = data?.query.q;
  return [
    { title: query ? `Search results for ${query} | OctaCam` : "Search CCTV equipment | OctaCam" },
    { name: "description", content: "Search published CCTV product names and model/SKU numbers, then filter by brand, category, PKR price, and availability." },
  ];
}

export function loader({ request }: Route.LoaderArgs) {
  return loadDiscovery(request);
}

export default function Search() {
  return <DiscoveryPage data={useLoaderData<typeof loader>()} path="/search" />;
}
