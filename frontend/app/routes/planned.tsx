import { Link, useLocation } from "react-router";
import { Container } from "~/components/layout/container";
import { plannedPages } from "~/config/storefront";

export function meta() {
  return [{ title: "Page in development | OctaCam" }];
}

export default function PlannedPage() {
  const { pathname } = useLocation();
  const page = plannedPages.find((entry) => entry.to === pathname);

  return (
    <Container size="reading" className="px-0 py-10 sm:py-16">
      <span className="text-sm font-semibold text-primary">In development</span>
      <h1 className="mt-3 text-[length:var(--font-size-heading)] font-bold tracking-[-0.035em]">
        {page?.label ?? "This page"} is coming soon
      </h1>
      <p className="mt-4 text-muted-foreground">
        {page?.detail ?? "This storefront screen is being built."} No shopping or booking action is available here yet.
      </p>
      <p className="mt-8"><Link to="/">Return to the development homepage</Link></p>
    </Container>
  );
}
