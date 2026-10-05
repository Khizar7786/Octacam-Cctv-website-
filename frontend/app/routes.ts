import { index, route, type RouteConfig } from "@react-router/dev/routes";
import { plannedPages } from "./config/storefront";

export default [
  index("routes/home.tsx"),
  route("foundation", "routes/foundation.tsx"),
  route("visual-foundation", "routes/visual-foundation.tsx"),
  ...plannedPages.map(({ to }) => route(to.slice(1), "routes/planned.tsx", {
    id: `planned-${to.slice(1).replaceAll("/", "-")}`,
  })),
  route("*", "routes/not-found.tsx"),
] satisfies RouteConfig;
