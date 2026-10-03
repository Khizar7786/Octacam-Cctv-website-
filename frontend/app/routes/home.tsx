import { Link } from "react-router";

export function meta() {
  return [{ title: "OctaCam | In development" }];
}

export default function Home() {
  return (
    <section className="space-y-5">
      <h1 className="text-3xl font-semibold">OctaCam is in development</h1>
      <p>The storefront is being prepared.</p>
      <p><Link to="/foundation">View frontend foundation</Link></p>
    </section>
  );
}
