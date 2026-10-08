import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useRouteLoaderData } from "react-router";
import { OctacamWordmark } from "~/components/brand/octacam-logo";
import { Container } from "~/components/layout/container";
import { HeaderSearch } from "~/components/layout/header-search";
import { useScrollHeader } from "~/components/layout/use-scroll-header";
import { StoreIcon, type StoreIconName } from "~/components/ui/store-icon";
import { brandLinks, categoryLinks, policyLinks } from "~/config/storefront";
import { cn } from "~/lib/utils";

type Panel = "menu" | "search" | null;

const plannedIcons: Partial<Record<string, StoreIconName>> = {
  "/cart": "cart",
  "/login": "account",
  "/surveys": "survey",
  "/contact": "contact",
};

function PlannedLink({
  label,
  to,
  onClick,
  compact = false,
  dark = false,
}: {
  label: string;
  to: string;
  onClick?: () => void;
  compact?: boolean;
  dark?: boolean;
}) {
  const iconName = plannedIcons[to];
  return (
    <Link
      className={cn(
        "min-h-11 items-center rounded-md text-sm font-semibold no-underline",
        compact ? "flex justify-between gap-2 px-3" : "inline-flex gap-1.5 px-2",
        dark
          ? "text-navigation-foreground hover:bg-navigation-hover hover:text-navigation-foreground focus-visible:outline-navigation-focus"
          : "text-foreground hover:bg-accent",
      )}
      onClick={onClick}
      to={to}
    >
      <span className="inline-flex items-center gap-2">
        {iconName ? <StoreIcon badge={dark || compact} name={iconName} /> : null}
        <span className={!compact && to === "/cart" ? "sr-only sm:not-sr-only" : undefined}>{label}</span>
      </span>
      <span className="rounded-sm bg-muted px-1.5 py-0.5 text-[0.625rem] font-semibold text-muted-foreground">Soon</span>
    </Link>
  );
}

function CatalogLink({ label, to, compact = false, dark = false, onClick }: { label: string; to: string; compact?: boolean; dark?: boolean; onClick?: () => void }) {
  return (
    <Link
      className={cn(
        "min-h-11 items-center rounded-md text-sm font-semibold no-underline",
        compact ? "flex px-3" : "inline-flex px-2",
        dark
          ? "text-navigation-foreground hover:bg-navigation-hover hover:text-navigation-foreground focus-visible:outline-navigation-focus"
          : "text-foreground hover:bg-accent",
      )}
      onClick={onClick}
      to={to}
    >{label}</Link>
  );
}

export function SiteHeader() {
  const active = useRouteLoaderData("root") as { brandLinks: { label: string; to: string }[]; categoryLinks: typeof categoryLinks[number][] } | undefined;
  const visibleBrandLinks = active?.brandLinks ?? brandLinks.filter((link) => link.to === "/brands");
  const visibleCategoryLinks = active?.categoryLinks ?? [];
  const [openPanel, setOpenPanel] = useState<Panel>(null);
  const { headerRef, mode } = useScrollHeader(openPanel !== null);
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
    <header className="site-header border-b border-border bg-card" data-panel-open={openPanel !== null} data-scroll-state={mode} ref={headerRef}>
      <div className="bg-header-strip">
        <Container className="py-1 text-center text-xs text-navigation-foreground">
          Storefront in development <span aria-hidden="true">·</span> Free site surveys are for Lahore; installation is quoted afterward.
        </Container>
      </div>

      <Container>
        <div className="flex min-h-[var(--header-row-height)] items-center justify-between gap-2 py-1 xl:grid xl:grid-cols-[minmax(0,1fr)_minmax(0,var(--header-search-max))_minmax(0,1fr)] xl:gap-4 2xl:gap-8">
          <Link aria-label="OctaCam home" className="inline-flex min-h-11 shrink-0 items-center rounded-md" onClick={() => setOpenPanel(null)} ref={logoLink} to="/">
            <OctacamWordmark />
          </Link>

          <div className="hidden min-w-0 xl:block">
            <HeaderSearch id="header-search" key={location.pathname + location.search} value={currentSearch} />
          </div>

          <div className="flex items-center gap-2 xl:justify-self-end">
            <button
              aria-label="Search"
              aria-controls="mobile-search"
              aria-expanded={openPanel === "search"}
              className="inline-flex min-h-11 items-center gap-1.5 rounded-md border border-border-strong px-2.5 text-sm font-semibold text-foreground xl:hidden"
              onClick={() => togglePanel("search")}
              ref={searchTrigger}
              type="button"
            >
              <StoreIcon name="search" /><span aria-hidden="true" className="hidden sm:inline">Search</span>
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
              <StoreIcon name="menu" /><span aria-hidden="true" className="hidden sm:inline">Menu</span>
            </button>
          </div>
        </div>
      </Container>

      <div className="hidden bg-navigation xl:block">
        <Container className="flex min-h-12 items-start justify-between gap-4 py-1">
          <nav aria-label="Storefront" className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1">
            {visibleBrandLinks.map((link) => <CatalogLink dark key={link.to} {...link} />)}
            <CatalogLink dark label="Shop all products" to="/shop" />
            {visibleCategoryLinks.length ? <span aria-hidden="true" className="mx-2 h-5 border-l border-navigation-foreground/30" /> : null}
            {visibleCategoryLinks.map((link) => <CatalogLink dark key={link.to} {...link} />)}
          </nav>
          <span className="shrink-0"><PlannedLink dark label="Free Lahore site survey" to="/surveys" /></span>
        </Container>
      </div>

      <div className="xl:hidden" hidden={openPanel !== "search"} id="mobile-search">
        <Container className="border-t border-border py-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-bold">Search the catalog</h2>
            <button className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border-strong px-3 text-sm font-semibold" onClick={closePanel} ref={searchClose} type="button"><StoreIcon name="close" />Close search</button>
          </div>
          <HeaderSearch className="mt-2" id="mobile-search-field" inputRef={searchInput} key={location.pathname + location.search} onSubmit={() => setOpenPanel(null)} value={currentSearch} />
        </Container>
      </div>

      <div className="bg-navigation text-navigation-foreground xl:hidden" hidden={openPanel !== "menu"} id="mobile-menu">
        <Container className="py-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="font-bold">Browse OctaCam</h2>
            <button className="inline-flex min-h-11 items-center gap-2 rounded-md border border-navigation-foreground/40 px-3 text-sm font-semibold hover:bg-navigation-hover focus-visible:outline-navigation-focus" onClick={closePanel} ref={menuClose} type="button"><StoreIcon badge name="close" />Close menu</button>
          </div>
          <nav aria-label="Mobile storefront" className="grid gap-3">
            <div>
              <h3 className="px-3 text-xs font-bold">Brands</h3>
              {visibleBrandLinks.map((link) => <CatalogLink compact dark key={link.to} onClick={() => setOpenPanel(null)} {...link} />)}
              <CatalogLink compact dark label="Shop all products" onClick={() => setOpenPanel(null)} to="/shop" />
            </div>
            <div>
              <h3 className="px-3 text-xs font-bold">Categories</h3>
              {visibleCategoryLinks.map((link) => <CatalogLink compact dark key={link.to} onClick={() => setOpenPanel(null)} {...link} />)}
            </div>
            <div className="border-t border-navigation-foreground/30 pt-3">
              {[
                { label: "Free Lahore site survey", to: "/surveys" },
                { label: "Account", to: "/login" },
                { label: "Cart", to: "/cart" },
                { label: "Contact", to: "/contact" },
                ...policyLinks,
              ].map((link) => <PlannedLink compact dark key={link.to} onClick={() => setOpenPanel(null)} {...link} />)}
            </div>
          </nav>
        </Container>
      </div>
    </header>
  );
}
