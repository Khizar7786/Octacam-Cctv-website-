import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
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

export function SiteHeader() {
  const [openPanel, setOpenPanel] = useState<Panel>(null);
  const menuTrigger = useRef<HTMLButtonElement>(null);
  const searchTrigger = useRef<HTMLButtonElement>(null);
  const menuClose = useRef<HTMLButtonElement>(null);
  const searchClose = useRef<HTMLButtonElement>(null);
  const logoLink = useRef<HTMLAnchorElement>(null);
  const location = useLocation();

  useEffect(() => {
    setOpenPanel(null);
  }, [location.pathname]);

  useEffect(() => {
    if (openPanel === "menu") menuClose.current?.focus();
    if (openPanel === "search") searchClose.current?.focus();
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

          <Link
            className="hidden min-h-12 min-w-0 items-center gap-3 rounded-md border border-input bg-background px-4 text-muted-foreground no-underline hover:border-primary hover:bg-accent xl:flex"
            to="/search"
          >
            <SearchIcon />
            <span className="truncate font-normal">Search products and model numbers</span>
            <span className="ml-auto shrink-0 text-xs font-semibold text-primary">Coming soon</span>
          </Link>

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
            {brandLinks.map((link) => <PlannedLink key={link.to} {...link} />)}
            <span aria-hidden="true" className="mx-2 h-5 border-l border-border" />
            {categoryLinks.map((link) => <PlannedLink key={link.to} {...link} />)}
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
          <Link className="mt-3 flex min-h-12 items-center gap-3 rounded-md border border-input px-3 text-muted-foreground no-underline" onClick={() => setOpenPanel(null)} to="/search">
            <SearchIcon /><span>Product and model search · Coming soon</span>
          </Link>
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
              {brandLinks.map((link) => <PlannedLink compact key={link.to} onClick={() => setOpenPanel(null)} {...link} />)}
            </div>
            <div>
              <h3 className="px-3 text-xs font-bold text-muted-foreground">Categories</h3>
              {categoryLinks.map((link) => <PlannedLink compact key={link.to} onClick={() => setOpenPanel(null)} {...link} />)}
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
