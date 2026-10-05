import { Link } from "react-router";

export function meta() {
  return [{ title: "Product details in development | OctaCam" }];
}

export default function ProductPending() {
  return (
    <section className="max-w-[var(--reading-max)] py-10">
      <p className="text-sm font-bold text-primary">In development</p>
      <h1 className="mt-3 text-[length:var(--font-size-heading)] font-bold">Product details are coming soon</h1>
      <p className="mt-4 text-muted-foreground">The detailed product screen and purchasing controls are being built. Browse the current catalog for published prices and availability.</p>
      <Link className="mt-6 inline-flex min-h-11 items-center" to="/shop">Return to shop</Link>
    </section>
  );
}
