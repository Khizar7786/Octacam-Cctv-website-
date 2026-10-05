import { useLoaderData } from "react-router";
import { DiscoveryPage } from "~/components/catalog/discovery-page";
import { loadDiscovery } from "~/features/catalog/discovery.server";
import type { Route } from "./+types/shop";

export function meta() {
  return [
    { title: "Shop CCTV equipment | OctaCam" },
    { name: "description", content: "Browse published CCTV cameras, recorders, storage, and accessories with current PKR prices and availability." },
  ];
}

export function loader({ request }: Route.LoaderArgs) {
  return loadDiscovery(request);
}

export default function Shop() {
  return <DiscoveryPage data={useLoaderData<typeof loader>()} path="/shop" />;
}
