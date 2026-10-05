import { index, route, type RouteConfig } from "@react-router/dev/routes";
import { plannedPages } from "./config/storefront";

export default [
  index("routes/home.tsx"),
  route("shop", "routes/shop.tsx"),
  route("search", "routes/search.tsx"),
  route("brands", "routes/brands.tsx"),
  route("brands/:slug", "routes/brand.tsx"),
  route("categories/:slug", "routes/category.tsx"),
  route("products/:slug", "routes/product-pending.tsx"),
  route("foundation", "routes/foundation.tsx"),
  route("visual-foundation", "routes/visual-foundation.tsx"),
  ...plannedPages.map(({ to }) => route(to.slice(1), "routes/planned.tsx", {
    id: `planned-${to.slice(1).replaceAll("/", "-")}`,
  })),
  route("*", "routes/not-found.tsx"),
] satisfies RouteConfig;
