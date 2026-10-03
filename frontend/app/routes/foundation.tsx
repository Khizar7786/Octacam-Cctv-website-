import { Link } from "react-router";
import type { Route } from "./+types/foundation";

export function meta() {
  return [{ title: "Frontend foundation | OctaCam" }];
}

export function loader() {
  return { message: "Server-rendered route loaded successfully." };
}

export default function Foundation({ loaderData }: Route.ComponentProps) {
  return (
    <section className="space-y-5">
      <h1 className="text-3xl font-semibold">Frontend foundation</h1>
      <p>{loaderData.message}</p>
      <p>This development page verifies direct route loading. The storefront will follow in later slices.</p>
      <p><Link to="/">Return home</Link></p>
    </section>
  );
}
