import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useLocation, useNavigate, useNavigation, useRevalidator } from "react-router";
import { ProductCard } from "./product-card";
import { Breadcrumbs } from "./catalog-listing";
import { buttonStyles } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  discoveryHref, discoveryPageHref, discoverySearchParams, parseDiscoveryQuery, validateTechnicalFilters, withCategory, withoutFilters,
  type DiscoveryErrors, type DiscoveryQuery, type DiscoveryScope, type ProductSort,
} from "~/features/catalog/discovery";
import type { loadDiscovery } from "~/features/catalog/discovery.server";
import type { DiscoveryFilterMetadata, FilterOption, SpecificationFilter } from "~/features/catalog/taxonomy";

type DiscoveryData = Awaited<ReturnType<typeof loadDiscovery>>;
type FilterField = "brand" | "category" | "min_price" | "max_price" | "availability";

const sortLabels: Record<ProductSort, string> = {
  relevance: "Relevance", price_asc: "Price: low to high", price_desc: "Price: high to low",
};

function FilterFields({
  prefix, draft, filters, errors, notice, scope, committedCategory, onChange, onSpecificationChange,
}: {
  prefix: string;
  draft: DiscoveryQuery;
  filters: DiscoveryFilterMetadata | null;
  errors: DiscoveryErrors;
  notice: string;
  scope: DiscoveryScope;
  committedCategory: string;
  onChange: (field: FilterField, value: string) => void;
  onSpecificationChange: (parameter: string, value: string) => void;
}) {
  function optionsFor(field: "brand" | "category"): FilterOption[] {
    const options = filters?.[field] ?? [];
    return draft[field] && !options.some((item) => item.value === draft[field])
      ? [...options, { value: draft[field], label: draft[field] }]
      : options;
  }

  return (
    <div className="grid gap-5">
      {notice ? <p className="rounded-md border border-info bg-info-surface p-3 text-sm" role="status">{notice}</p> : null}
      {(["brand", "category"] as const).filter((field) => !(field in scope)).map((field) => (
        <div key={field}>
          <label className="mb-1 block text-sm font-semibold" htmlFor={`${prefix}-${field}`}>{field === "brand" ? "Brand" : "Category"}</label>
          <select aria-describedby={errors[field] ? `${prefix}-${field}-error` : undefined} aria-invalid={Boolean(errors[field])} className="min-h-11 w-full rounded-md border border-input bg-background px-3 text-foreground" id={`${prefix}-${field}`} name={field} onChange={(event) => onChange(field, event.target.value)} value={draft[field]}>
            <option value="">All {field === "brand" ? "brands" : "categories"}</option>
            {optionsFor(field).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          {errors[field] ? <p className="mt-1 text-sm text-error" id={`${prefix}-${field}-error`}>{errors[field]}</p> : null}
        </div>
      ))}
      <fieldset className="grid gap-3">
        <legend className="mb-1 text-sm font-semibold">Selling price (PKR)</legend>
        <div className="grid grid-cols-2 gap-3">
          {(["min_price", "max_price"] as const).map((field) => (
            <div key={field}>
              <label className="mb-1 block text-xs font-semibold text-muted-foreground" htmlFor={`${prefix}-${field}`}>{field === "min_price" ? "Minimum" : "Maximum"}</label>
              <Input aria-describedby={errors[field] ? `${prefix}-${field}-error` : undefined} aria-invalid={Boolean(errors[field])} autoComplete="off" id={`${prefix}-${field}`} inputMode="decimal" onChange={(event) => onChange(field, event.target.value)} placeholder="0.00" type="text" value={draft[field]} />
              {errors[field] ? <p className="mt-1 text-sm text-error" id={`${prefix}-${field}-error`}>{errors[field]}</p> : null}
            </div>
          ))}
        </div>
      </fieldset>
      <div>
        <label className="mb-1 block text-sm font-semibold" htmlFor={`${prefix}-availability`}>Availability</label>
        <select aria-describedby={errors.availability ? `${prefix}-availability-error` : undefined} aria-invalid={Boolean(errors.availability)} className="min-h-11 w-full rounded-md border border-input bg-background px-3 text-foreground" id={`${prefix}-availability`} onChange={(event) => onChange("availability", event.target.value)} value={draft.availability}>
          <option value="">All products</option>
          <option value="in_stock">In stock</option>
          <option value="out_of_stock">Out of stock</option>
        </select>
        {errors.availability ? <p className="mt-1 text-sm text-error" id={`${prefix}-availability-error`}>{errors.availability}</p> : null}
      </div>
      {draft.category !== committedCategory ? (
        <p className="text-sm text-muted-foreground">Apply filters to load technical options for the selected category.</p>
      ) : draft.category && filters?.specifications.length ? (
        <fieldset className="grid gap-4 border-t border-border pt-5">
          <legend className="text-sm font-semibold">Technical specifications</legend>
          {filters.specifications.map((definition) => (
            <SpecificationField definition={definition} draft={draft} errors={errors} key={definition.key} onChange={onSpecificationChange} prefix={prefix} />
          ))}
        </fieldset>
      ) : draft.category ? null : (
        <p className="text-sm text-muted-foreground">Choose a category to see relevant technical filters.</p>
      )}
    </div>
  );
}

function SpecificationField({ definition, draft, errors, prefix, onChange }: {
  definition: SpecificationFilter;
  draft: DiscoveryQuery;
  errors: DiscoveryErrors;
  prefix: string;
  onChange: (parameter: string, value: string) => void;
}) {
  const base = `spec_${definition.key}`;
  const title = `${definition.label}${definition.unit ? ` (${definition.unit})` : ""}`;
  if (definition.type === "choice" || definition.type === "boolean") {
    const selected = draft.specifications[base] ?? "";
    const options = definition.options.map((option) => ({ value: String(option.value), label: option.label }));
    if (selected && !options.some((option) => option.value === selected)) options.push({ value: selected, label: selected });
    return (
      <div>
        <label className="mb-1 block text-sm font-semibold" htmlFor={`${prefix}-${base}`}>{title}</label>
        <select aria-describedby={errors[base] ? `${prefix}-${base}-error` : undefined} aria-invalid={Boolean(errors[base])} className="min-h-11 w-full rounded-md border border-input bg-background px-3 text-foreground" id={`${prefix}-${base}`} onChange={(event) => onChange(base, event.target.value)} value={selected}>
          <option value="">Any {definition.label.toLowerCase()}</option>
          {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        {errors[base] ? <p className="mt-1 text-sm text-error" id={`${prefix}-${base}-error`}>{errors[base]}</p> : null}
      </div>
    );
  }
  return (
    <fieldset className="grid gap-2">
      <legend className="text-sm font-semibold">{title}</legend>
      <p className="text-xs text-muted-foreground">Observed range: {definition.min} to {definition.max}{definition.unit ? ` ${definition.unit}` : ""}</p>
      <div className="grid grid-cols-2 gap-3">
        {(["min", "max"] as const).map((bound) => {
          const parameter = `${base}_${bound}`;
          return (
            <div key={bound}>
              <label className="mb-1 block text-xs font-semibold text-muted-foreground" htmlFor={`${prefix}-${parameter}`}>{bound === "min" ? "Minimum" : "Maximum"}</label>
              <Input aria-describedby={errors[parameter] ? `${prefix}-${parameter}-error` : undefined} aria-invalid={Boolean(errors[parameter])} autoComplete="off" id={`${prefix}-${parameter}`} inputMode={definition.type === "integer_range" ? "numeric" : "decimal"} onChange={(event) => onChange(parameter, event.target.value)} type="text" value={draft.specifications[parameter] ?? ""} />
              {errors[parameter] ? <p className="mt-1 text-sm text-error" id={`${prefix}-${parameter}-error`}>{errors[parameter]}</p> : null}
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}

export function DiscoveryPage({ data, path, scope = {}, heading }: {
  data: DiscoveryData;
  path: string;
  scope?: DiscoveryScope;
  heading?: { eyebrow: string; title: string; description: string; breadcrumbs: { label: string; to?: string }[] };
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const focusAfterChip = useRef(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [draft, setDraft] = useState<DiscoveryQuery>(data.query);
  const [draftErrors, setDraftErrors] = useState<DiscoveryErrors>(data.state === "invalid" ? data.errors : {});
  const [scopeNotice, setScopeNotice] = useState("");
  const filters = "filters" in data ? data.filters ?? null : null;
  const loading = navigation.state === "loading" || revalidator.state === "loading";
  const hasFilters = Boolean((!scope.brand && data.query.brand) || (!scope.category && data.query.category) || data.query.min_price || data.query.max_price || data.query.availability || Object.keys(data.query.specifications).length);
  const invalidField = data.state === "invalid" && Object.keys(data.errors).some((field) => field !== "page" && field !== "url");

  useEffect(() => {
    setDraft(data.query);
    setDraftErrors(data.state === "invalid" ? data.errors : {});
    setScopeNotice("");
    setMobileOpen(false);
    if (focusAfterChip.current) {
      focusAfterChip.current = false;
      document.querySelector<HTMLButtonElement>("[data-filter-chip]")?.focus();
      if (!(document.activeElement instanceof HTMLButtonElement && document.activeElement.hasAttribute("data-filter-chip"))) searchRef.current?.focus();
    }
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!mobileOpen) return;
    closeRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, [mobileOpen]);

  function closeMobile() {
    setMobileOpen(false);
    triggerRef.current?.focus();
  }

  function dialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeMobile();
    }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href]")];
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }

  function changeField(field: FilterField, value: string) {
    if (field === "category" && value !== draft.category) {
      const clearedBrand = Boolean(draft.brand && !scope.brand);
      const clearedSpecifications = Object.keys(draft.specifications).length > 0;
      setDraft((current) => withCategory(current, value, scope));
      setDraftErrors({});
      setScopeNotice(clearedSpecifications
        ? `Technical filters${clearedBrand ? " and brand selection" : ""} cleared because the category changed.`
        : clearedBrand ? "Brand selection cleared because the category changed." : "");
      return;
    }
    setDraft((current) => ({ ...current, [field]: value }));
    setDraftErrors((current) => ({ ...current, [field]: undefined }));
  }

  function changeSpecification(parameter: string, value: string) {
    setDraft((current) => {
      const specifications = { ...current.specifications };
      if (value) specifications[parameter] = value;
      else delete specifications[parameter];
      return { ...current, specifications };
    });
    setDraftErrors((current) => ({ ...current, [parameter]: undefined }));
  }

  function apply(event?: FormEvent) {
    event?.preventDefault();
    const parsed = parseDiscoveryQuery(discoverySearchParams({ ...draft, page: 1 }));
    const errors = { ...parsed.errors, ...validateTechnicalFilters(parsed.query, filters?.specifications ?? []) };
    if (Object.keys(errors).length) {
      setDraftErrors(errors);
      return;
    }
    if (mobileOpen) triggerRef.current?.focus();
    setMobileOpen(false);
    navigate(discoveryHref(path, parsed.query, scope), { state: scopeNotice ? { catalogScopeNotice: scopeNotice } : null });
  }

  function clearDraft() {
    setDraft((current) => withoutFilters(current, scope));
    setDraftErrors({});
    setScopeNotice("");
  }

  function removeFilter(field: string) {
    focusAfterChip.current = true;
    if (field === "category") {
      const clearedSpecifications = Object.keys(data.query.specifications).length > 0;
      const clearedBrand = Boolean(data.query.brand && !scope.brand);
      const notice = clearedSpecifications ? `Technical filters${clearedBrand ? " and brand selection" : ""} cleared because the category was removed.` : clearedBrand ? "Brand selection cleared because the category was removed." : "";
      navigate(discoveryHref(path, withCategory(data.query, "", scope), scope), { state: notice ? { catalogScopeNotice: notice } : null });
    }
    else if (field.startsWith("spec_")) {
      const specifications = { ...data.query.specifications };
      delete specifications[field];
      navigate(discoveryHref(path, { ...data.query, specifications, page: 1 }, scope));
    } else navigate(discoveryHref(path, { ...data.query, [field]: "", page: 1 }, scope));
  }

  function filterLabel(field: "brand" | "category", slug: string) {
    return filters?.[field].find((item) => item.value === slug)?.label ?? slug;
  }

  const chips: { field: string; label: string }[] = [
    ...(!scope.brand && data.query.brand ? [{ field: "brand" as const, label: `Brand: ${filterLabel("brand", data.query.brand)}` }] : []),
    ...(!scope.category && data.query.category ? [{ field: "category" as const, label: `Category: ${filterLabel("category", data.query.category)}` }] : []),
    ...(data.query.min_price ? [{ field: "min_price" as const, label: `From PKR ${data.query.min_price}` }] : []),
    ...(data.query.max_price ? [{ field: "max_price" as const, label: `To PKR ${data.query.max_price}` }] : []),
    ...(data.query.availability ? [{ field: "availability" as const, label: data.query.availability === "in_stock" ? "In stock" : "Out of stock" }] : []),
    ...Object.entries(data.query.specifications).map(([field, value]) => {
      const definition = filters?.specifications.find((item) => field === `spec_${item.key}` || field === `spec_${item.key}_min` || field === `spec_${item.key}_max`);
      const option = definition?.type === "choice" || definition?.type === "boolean" ? definition.options.find((item) => String(item.value) === value) : null;
      const label = definition?.label ?? field.replace(/^spec_/, "").replaceAll("_", " ");
      const bound = definition?.type === "integer_range" || definition?.type === "decimal_range"
        ? field === `spec_${definition.key}_min` ? " from" : " to"
        : "";
      return { field, label: `${label}${bound}: ${option?.label ?? value}${definition?.unit ? ` ${definition.unit}` : ""}` };
    }),
  ];

  return (
    <div className="space-y-8">
      {heading ? <Breadcrumbs items={heading.breadcrumbs} /> : null}
      <header className="max-w-3xl">
        <p className="text-sm font-bold text-primary">{heading?.eyebrow ?? "OctaCam catalog"}</p>
        <h1 className="mt-2 text-[length:var(--font-size-heading)] font-bold leading-tight">{heading?.title ?? (path === "/search" ? "Search CCTV equipment" : "Shop CCTV equipment")}</h1>
        <p className="mt-3 text-muted-foreground">{heading?.description ?? "Search product names or exact and partial model/SKU numbers. Prices and availability come from current published records."}</p>
      </header>
      {typeof location.state?.catalogScopeNotice === "string" ? <p className="rounded-md border border-info bg-info-surface p-3 text-sm" role="status">{location.state.catalogScopeNotice}</p> : null}

      <form aria-label="Catalog search" className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={apply} role="search">
        <div className="min-w-0 flex-1">
          <label className="mb-1 block text-sm font-semibold" htmlFor="catalog-search">Product name or model/SKU</label>
          <Input aria-describedby={draftErrors.q ? "catalog-search-error" : undefined} aria-invalid={Boolean(draftErrors.q)} autoComplete="off" id="catalog-search" onChange={(event) => { setDraft((current) => ({ ...current, q: event.target.value })); setDraftErrors((current) => ({ ...current, q: undefined })); }} placeholder="Search cameras, recorders, or a model number" ref={searchRef} type="search" value={draft.q} />
          {draftErrors.q ? <p className="mt-1 text-sm text-error" id="catalog-search-error">{draftErrors.q}</p> : null}
        </div>
        <button className={buttonStyles({ className: "sm:mb-0" })} type="submit">Search products</button>
      </form>

      <div className="flex flex-wrap items-center justify-between gap-3 lg:hidden">
        <button aria-controls="mobile-catalog-filters" aria-expanded={mobileOpen} aria-haspopup="dialog" className={buttonStyles({ variant: "outline" })} onClick={() => { setDraft(data.query); setDraftErrors({}); setScopeNotice(""); setMobileOpen(true); }} ref={triggerRef} type="button">Filters{chips.length ? ` (${chips.length})` : ""}</button>
        <SortControl id="mobile-catalog-sort" onChange={(sort) => navigate(discoveryHref(path, { ...data.query, sort, page: 1 }, scope))} sort={data.query.sort} />
      </div>

      {chips.length ? (
        <div aria-label="Active filters" className="flex flex-wrap items-center gap-2">
          {chips.map((chip) => <button aria-label={`Remove ${chip.label} filter`} className="inline-flex min-h-11 items-center gap-2 rounded-full border border-border-strong bg-card px-3 text-sm hover:bg-accent" data-filter-chip key={chip.field} onClick={() => removeFilter(chip.field)} type="button">{chip.label}<span aria-hidden="true">×</span></button>)}
          <Link className="inline-flex min-h-11 items-center px-2 text-sm" onClick={() => { focusAfterChip.current = true; }} to={discoveryHref(path, withoutFilters(data.query, scope), scope)}>Clear filters</Link>
        </div>
      ) : null}

      {data.state === "invalid" ? (
        <section className="rounded-lg border border-warning bg-warning-surface p-6" role="alert">
          <h2 className="text-lg font-bold">This catalog selection is unavailable</h2>
          <p className="mt-2 text-sm">{data.errors.url ?? data.errors.page ?? "Review the highlighted search or filter values."}</p>
          {Object.entries(data.errors).filter(([key]) => key !== "url" && key !== "page").map(([key, message]) => <p className="mt-1 text-sm" key={key}>{key.replaceAll("_", " ")}: {message}</p>)}
          <Link className="mt-3 inline-flex min-h-11 items-center" to={invalidField ? path : discoveryHref(path, { ...data.query, page: 1 }, scope)}>{invalidField ? "Start a new search" : "Return to page 1"}</Link>
        </section>
      ) : null}
      {data.state === "error" ? (
        <section className="rounded-lg border border-error bg-error-surface p-6" role="alert">
          <h2 className="text-lg font-bold">Products could not be loaded</h2>
          <p className="mt-2 text-sm">Your search and filters remain in the address. Please try again.</p>
          <button className={buttonStyles({ variant: "outline", className: "mt-4" })} disabled={loading} onClick={() => revalidator.revalidate()} type="button">Try again</button>
        </section>
      ) : null}

      <div className="lg:grid lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-8">
        <aside aria-label="Catalog filters" className="hidden self-start rounded-lg border border-border bg-card p-5 lg:block">
          <h2 className="mb-5 text-lg font-bold">Filter products</h2>
          <form onSubmit={apply}>
            <FilterFields committedCategory={data.query.category} draft={draft} errors={draftErrors} filters={filters} notice={scopeNotice} onChange={changeField} onSpecificationChange={changeSpecification} prefix="desktop" scope={scope} />
            <div className="mt-6 grid gap-2">
              <button className={buttonStyles()} type="submit">Apply filters</button>
              <button className={buttonStyles({ variant: "outline" })} onClick={clearDraft} type="button">Clear filters</button>
            </div>
          </form>
        </aside>

        {data.state === "ready" ? (
          <section aria-busy={loading} aria-labelledby="products-heading" className="min-w-0">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold" id="products-heading">{data.query.q ? `Results for “${data.query.q}”` : "Published products"}</h2>
                <p className="mt-1 text-sm text-muted-foreground" role="status">{data.catalog.count} {data.catalog.count === 1 ? "product" : "products"} · Page {data.query.page}</p>
              </div>
              <div className="hidden lg:block"><SortControl id="desktop-catalog-sort" onChange={(sort) => navigate(discoveryHref(path, { ...data.query, sort, page: 1 }, scope))} sort={data.query.sort} /></div>
            </div>
            {data.catalog.count === 0 ? (
              <div className="rounded-lg border border-border bg-card p-6 sm:p-10">
                <h3 className="text-lg font-bold">{data.query.q || hasFilters ? "No matching products" : heading ? "No published products in this selection" : "No published products yet"}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{data.query.q || hasFilters ? "Try a broader model or product name, remove a filter, or browse the catalog." : "The catalog is empty right now. Return later to see equipment after it has been published."}</p>
                <div className="mt-4 flex flex-wrap gap-4 text-sm">
                  {hasFilters ? <Link className="inline-flex min-h-11 items-center" to={discoveryHref(path, withoutFilters(data.query, scope), scope)}>Clear filters</Link> : null}
                  <Link className="inline-flex min-h-11 items-center" to="/shop">Browse all products</Link>
                  <Link className="inline-flex min-h-11 items-center" to="/#categories">Browse categories</Link>
                </div>
              </div>
            ) : data.catalog.results.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {data.catalog.results.map((product) => <ProductCard key={product.id} product={product} />)}
              </div>
            ) : <p className="rounded-lg border border-border bg-card p-6">There are no products on this page. <Link to={discoveryHref(path, { ...data.query, page: 1 }, scope)}>Return to page 1</Link>.</p>}
            {data.catalog.previous || data.catalog.next ? (
              <nav aria-label="Catalog pages" className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
                {data.catalog.previous ? <Link className={buttonStyles({ variant: "outline" })} rel="prev" to={discoveryPageHref(path, data.query, data.catalog.previous, scope)}>Previous page</Link> : <span />}
                {data.catalog.next ? <Link className={buttonStyles({ variant: "outline" })} rel="next" to={discoveryPageHref(path, data.query, data.catalog.next, scope)}>Next page</Link> : null}
              </nav>
            ) : null}
          </section>
        ) : null}
      </div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 bg-foreground/60 p-0 sm:p-4 lg:hidden">
          <div aria-label="Filter products" aria-modal="true" className="ml-auto flex h-full w-full max-w-md flex-col bg-card shadow-lg sm:rounded-lg" id="mobile-catalog-filters" onKeyDown={dialogKeyDown} ref={dialogRef} role="dialog">
            <div className="flex items-center justify-between gap-3 border-b border-border p-4">
              <h2 className="text-lg font-bold">Filter products</h2>
              <button className={buttonStyles({ variant: "ghost" })} onClick={closeMobile} ref={closeRef} type="button">Close</button>
            </div>
            <form className="flex min-h-0 flex-1 flex-col" onSubmit={apply}>
              <div className="min-h-0 flex-1 overflow-y-auto p-4"><FilterFields committedCategory={data.query.category} draft={draft} errors={draftErrors} filters={filters} notice={scopeNotice} onChange={changeField} onSpecificationChange={changeSpecification} prefix="mobile" scope={scope} /></div>
              <div className="flex gap-3 border-t border-border bg-card p-4">
                <button className={buttonStyles({ variant: "outline", className: "flex-1" })} onClick={clearDraft} type="button">Clear</button>
                <button className={buttonStyles({ className: "flex-1" })} type="submit">Apply filters</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
      {revalidator.state === "loading" ? <p className="sr-only" role="status">Loading products...</p> : null}
    </div>
  );
}

function SortControl({ id, sort, onChange }: { id: string; sort: ProductSort; onChange: (sort: ProductSort) => void }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-semibold" htmlFor={id}>Sort by</label>
      <select className="min-h-11 rounded-md border border-input bg-background px-3 text-foreground" id={id} onChange={(event) => onChange(event.target.value as ProductSort)} value={sortLabels[sort] ? sort : "relevance"}>
        {(Object.entries(sortLabels) as [ProductSort, string][]).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </div>
  );
}
