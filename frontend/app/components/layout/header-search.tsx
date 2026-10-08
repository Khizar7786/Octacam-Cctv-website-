import type { Ref } from "react";
import { StoreIcon } from "~/components/ui/store-icon";
import { cn } from "~/lib/utils";

export function HeaderSearch({ id, value, inputRef, onSubmit, className }: {
  id: string;
  value: string;
  inputRef?: Ref<HTMLInputElement>;
  onSubmit?: () => void;
  className?: string;
}) {
  return (
    <form action="/search" aria-label="Site search" className={cn("header-search flex w-full min-w-0 items-center gap-2 rounded-full bg-background p-0.5 pl-4", className)} method="get" onSubmit={onSubmit} role="search">
      <label className="sr-only" htmlFor={id}>Search product names and model numbers</label>
      <input className="min-h-11 min-w-0 flex-1 border-0 bg-transparent px-1 text-foreground focus-visible:outline-none" defaultValue={value} id={id} maxLength={120} name="q" placeholder="Search products and model numbers" ref={inputRef} type="search" />
      <button aria-label="Search products" className="inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-navigation text-navigation-foreground hover:bg-navigation-hover" type="submit">
        <StoreIcon inheritColor name="search" />
      </button>
    </form>
  );
}
