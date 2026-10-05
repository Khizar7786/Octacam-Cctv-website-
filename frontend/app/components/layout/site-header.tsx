import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useRouteLoaderData } from "react-router";
import { OctacamLogo } from "~/components/brand/octacam-logo";
import { Container } from "~/components/layout/container";
import { brandLinks, categoryLinks, policyLinks } from "~/config/storefront";

type Panel = "menu" | "search" | null;

function SearchIcon() {
  return (
    <svg aria-hidden="true" className="size-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <circle cx="10.8" cy="10.8" r="6.8" />
      <path d="m16 16 5 5" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg aria-hidden="true" className="size-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M3 6h18M3 12h18M3 18h18" />
    </svg>
  );
}

function PlannedLink({
  label,
  to,
  onClick,
  compact = false,
}: {
  label: string;
  to: string;
  onClick?: () => void;
  compact?: boolean;
}) {
  return (
    <Link
      className={compact
        ? "flex min-h-11 items-center justify-between gap-2 rounded-md px-3 text-sm font-semibold text-foreground no-underline hover:bg-accent"
        : "inline-flex min-h-11 items-center gap-1.5 rounded-md px-2 text-sm font-semibold text-foreground no-underline hover:bg-accent"}
      onClick={onClick}
      to={to}
    >
      <span>{label}</span>
      <span className="rounded-sm bg-muted px-1.5 py-0.5 text-[0.625rem] font-semibold text-muted-foreground">Soon</span>
    </Link>
  );
}

function CatalogLink({ label, to, compact = false, onClick }: { label: string; to: string; compact?: boolean; onClick?: () => void }) {
  return (
    <Link
      className={compact
        ? "flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-foreground no-underline hover:bg-accent"
        : "inline-flex min-h-11 items-center rounded-md px-2 text-sm font-semibold text-foreground no-underline hover:bg-accent"}
      onClick={onClick}
      to={to}
    >{label}</Link>
  );
}

export function SiteHeader() {
  const active = useRouteLoaderData("root") as { brandLinks: typeof brandLinks[number][]; categoryLinks: typeof categoryLinks[number][] } | undefined;
  const visibleBrandLinks = active?.brandLinks ?? brandLinks.filter((link) => link.to === "/brands");
  const visibleCategoryLinks = active?.categoryLinks ?? [];
  const [openPanel, setOpenPanel] = useState<Panel>(null);
  const menuTrigger = useRef<HTMLButtonElement>(null);
  const searchTrigger = useRef<HTMLButtonElement>(null);
  const menuClose = useRef<HTMLButtonElement>(null);
  const searchClose = useRef<HTMLButtonElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const logoLink = useRef<HTMLAnchorElement>(null);
  const location = useLocation();
  const currentSearch = location.pathname === "/search" ? new URLSearchParams(location.search).get("q") ?? "" : "";

  useEffect(() => {
    setOpenPanel(null);
  }, [location.pathname]);

  useEffect(() => {
    if (openPanel === "menu") menuClose.current?.focus();
    if (openPanel === "search") searchInput.current?.focus();
  }, [openPanel]);

  useEffect(() => {
    if (!openPanel) return;
    function onEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      const trigger = openPanel === "menu" ? menuTrigger.current : searchTrigger.current;
      setOpenPanel(null);
      trigger?.focus();
    }
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [openPanel]);

  useEffect(() => {
    if (!openPanel) return;
    const desktop = window.matchMedia("(min-width: 80rem)");
    function onViewportChange() {
      if (!desktop.matches) return;
      const panel = document.getElementById(openPanel === "menu" ? "mobile-menu" : "mobile-search");
      if (panel?.contains(document.activeElement)) logoLink.current?.focus();
      setOpenPanel(null);
    }
    desktop.addEventListener("change", onViewportChange);
    return () => desktop.removeEventListener("change", onViewportChange);
  }, [openPanel]);

  function closePanel() {
    const trigger = openPanel === "menu" ? menuTrigger.current : searchTrigger.current;
    setOpenPanel(null);
    trigger?.focus();
  }

  function togglePanel(panel: Exclude<Panel, null>) {
    setOpenPanel((current) => current === panel ? null : panel);
  }

  return (
    <header className="border-b border-border bg-card">
      <div className="border-b border-border bg-muted/50">
        <Container className="py-2 text-xs text-muted-foreground">
          Storefront in development <span aria-hidden="true">·</span> Free site surveys are for Lahore; installation is quoted afterward.
        </Container>
      </div>

      <Container>
        <div className="flex min-h-24 items-center justify-between gap-3 py-3 xl:grid xl:grid-cols-[auto_minmax(0,1fr)_auto] xl:gap-8">
          <Link className="block w-20 shrink-0 rounded-md xl:w-24" onClick={() => setOpenPanel(null)} ref={logoLink} to="/">
            <OctacamLogo alt="OctaCam home" />
          </Link>

          <form action="/search" aria-label="Site search" className="hidden min-w-0 items-center gap-2 xl:flex" method="get" role="search">
            <label className="sr-only" htmlFor="header-search">Search product names and model numbers</label>
            <input className="min-h-12 min-w-0 flex-1 rounded-md border border-input bg-background px-4 text-foreground" defaultValue={currentSearch} id="header-search" key={location.pathname + location.search} maxLength={120} name="q" placeholder="Search products and model numbers" type="search" />
            <button className="min-h-12 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary-hover" type="submit">Search</button>
          </form>

          <div className="flex items-center gap-2">
            <button
              aria-label="Search"
              aria-controls="mobile-search"
              aria-expanded={openPanel === "search"}
              className="inline-flex min-h-11 items-center gap-1.5 rounded-md border border-border-strong px-2.5 text-sm font-semibold text-foreground xl:hidden"
              onClick={() => togglePanel("search")}
              ref={searchTrigger}
              type="button"
            >
              <SearchIcon /><span aria-hidden="true" className="hidden sm:inline">Search</span>
            </button>
            <span className="hidden xl:inline-flex"><PlannedLink label="Account" to="/login" /></span>
            <PlannedLink label="Cart" to="/cart" />
            <button
              aria-label="Menu"
              aria-controls="mobile-menu"
              aria-expanded={openPanel === "menu"}
              className="inline-flex min-h-11 items-center gap-1.5 rounded-md border border-border-strong px-2.5 text-sm font-semibold text-foreground xl:hidden"
              onClick={() => togglePanel("menu")}
              ref={menuTrigger}
              type="button"
            >
              <MenuIcon /><span aria-hidden="true" className="hidden sm:inline">Menu</span>
            </button>
          </div>
        </div>
      </Container>

      <div className="hidden border-t border-border xl:block">
        <Container className="flex min-h-14 items-center justify-between gap-4">
          <nav aria-label="Storefront" className="flex flex-wrap items-center gap-x-1">
            {visibleBrandLinks.map((link) => <CatalogLink key={link.to} {...link} />)}
            <span aria-hidden="true" className="mx-2 h-5 border-l border-border" />
            {visibleCategoryLinks.length ? visibleCategoryLinks.map((link) => <CatalogLink key={link.to} {...link} />) : <CatalogLink label="Shop all products" to="/shop" />}
          </nav>
          <PlannedLink label="Free Lahore site survey" to="/surveys" />
        </Container>
      </div>

      <div className="xl:hidden" hidden={openPanel !== "search"} id="mobile-search">
        <Container className="border-t border-border py-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-bold">Search the catalog</h2>
            <button className="min-h-11 rounded-md border border-border-strong px-3 text-sm font-semibold" onClick={closePanel} ref={searchClose} type="button">Close search</button>
          </div>
          <form action="/search" aria-label="Mobile site search" className="mt-3 grid gap-2" method="get" onSubmit={() => setOpenPanel(null)} role="search">
            <label className="text-sm font-semibold" htmlFor="mobile-search-field">Product name or model/SKU</label>
            <input className="min-h-12 w-full rounded-md border border-input bg-background px-3 text-foreground" defaultValue={currentSearch} id="mobile-search-field" key={location.pathname + location.search} maxLength={120} name="q" placeholder="Search products and model numbers" ref={searchInput} type="search" />
            <button className="min-h-11 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary-hover" type="submit">Search products</button>
          </form>
        </Container>
      </div>

      <div className="xl:hidden" hidden={openPanel !== "menu"} id="mobile-menu">
        <Container className="border-t border-border py-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="font-bold">Browse OctaCam</h2>
            <button className="min-h-11 rounded-md border border-border-strong px-3 text-sm font-semibold" onClick={closePanel} ref={menuClose} type="button">Close menu</button>
          </div>
          <nav aria-label="Mobile storefront" className="grid gap-5">
            <div>
              <h3 className="px-3 text-xs font-bold text-muted-foreground">Brands</h3>
              {visibleBrandLinks.map((link) => <CatalogLink compact key={link.to} onClick={() => setOpenPanel(null)} {...link} />)}
            </div>
            <div>
              <h3 className="px-3 text-xs font-bold text-muted-foreground">Categories</h3>
              {visibleCategoryLinks.length ? visibleCategoryLinks.map((link) => <CatalogLink compact key={link.to} onClick={() => setOpenPanel(null)} {...link} />) : <CatalogLink compact label="Shop all products" onClick={() => setOpenPanel(null)} to="/shop" />}
            </div>
            <div className="border-t border-border pt-3">
              {[
                { label: "Free Lahore site survey", to: "/surveys" },
                { label: "Account", to: "/login" },
                { label: "Cart", to: "/cart" },
                { label: "Contact", to: "/contact" },
                ...policyLinks,
              ].map((link) => <PlannedLink compact key={link.to} onClick={() => setOpenPanel(null)} {...link} />)}
            </div>
          </nav>
        </Container>
      </div>
    </header>
  );
}
