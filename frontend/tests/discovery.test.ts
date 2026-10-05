import assert from "node:assert/strict";
import { test } from "node:test";
import { createMemoryRouter } from "react-router";
import {
  discoveryHref, discoveryPageHref, parseDiscoveryQuery, validateTechnicalFilters, withCategory, withoutFilters,
} from "../app/features/catalog/discovery.ts";
import { apiPath } from "../app/lib/api/client.ts";
import type { SpecificationFilter } from "../app/features/catalog/taxonomy.ts";

const cameraSpecifications: SpecificationFilter[] = [
  { key: "resolution", label: "Resolution", type: "choice", unit: null, options: [{ value: "2mp", label: "2 MP" }] },
  { key: "outdoor", label: "Outdoor", type: "boolean", unit: null, options: [{ value: true, label: "Yes" }, { value: false, label: "No" }] },
  { key: "ir_distance", label: "IR distance", type: "decimal_range", unit: "m", min: "20.0000", max: "50.0000" },
];

test("accepts the backend search/filter/sort contract and retains decimal strings", () => {
  const { query, errors } = parseDiscoveryQuery(new URLSearchParams("q=DS-2CE&brand=hikvision&category=cameras&min_price=5000.00&max_price=20000.50&availability=out_of_stock&sort=price_desc&page=2"));
  assert.deepEqual(errors, {});
  assert.equal(query.q, "DS-2CE");
  assert.equal(query.min_price, "5000.00");
  assert.equal(discoveryHref("/search", query), "/search?q=DS-2CE&brand=hikvision&category=cameras&min_price=5000.00&max_price=20000.50&availability=out_of_stock&sort=price_desc&page=2");
  assert.equal(discoveryPageHref("/search", query, apiPath("/api/v1/catalog/products/?page=3&brand=wrong")), "/search?q=DS-2CE&brand=hikvision&category=cameras&min_price=5000.00&max_price=20000.50&availability=out_of_stock&sort=price_desc&page=3");
  assert.equal(discoveryHref("/search", withoutFilters(query)), "/search?q=DS-2CE&sort=price_desc");
  assert.equal(discoveryHref("/brands/hikvision", query, { brand: "hikvision" }), "/brands/hikvision?q=DS-2CE&category=cameras&min_price=5000.00&max_price=20000.50&availability=out_of_stock&sort=price_desc&page=2");
  assert.equal(discoveryHref("/brands/hikvision", withoutFilters(query, { brand: "hikvision" }), { brand: "hikvision" }), "/brands/hikvision?q=DS-2CE&sort=price_desc");
});

test("rejects invalid amounts, ranges, repeated or unknown options, and page numbers before API calls", () => {
  for (const [search, field] of [
    ["min_price=1.234", "min_price"], ["min_price=-1", "min_price"],
    ["min_price=200&max_price=199.99", "max_price"], ["sort=newest", "sort"],
    ["availability=sold", "availability"], ["page=0", "page"],
    ["q=a&q=b", "url"], ["spec_resolution=4mp", "category"],
  ]) {
    const { errors } = parseDiscoveryQuery(new URLSearchParams(search));
    assert.ok(errors[field as keyof typeof errors], `${search} should fail at ${field}`);
  }
});

test("technical filters follow metadata types and exact backend parameter names", () => {
  const { query, errors } = parseDiscoveryQuery(new URLSearchParams("q=DS-2CE&category=cameras&brand=hikvision&spec_resolution=2mp&spec_outdoor=true&spec_ir_distance_min=20.0000&spec_ir_distance_max=25&sort=price_asc&page=2"));
  assert.deepEqual(errors, {});
  assert.deepEqual(validateTechnicalFilters(query, cameraSpecifications), {});
  assert.equal(discoveryHref("/search", query), "/search?q=DS-2CE&brand=hikvision&category=cameras&spec_ir_distance_max=25&spec_ir_distance_min=20.0000&spec_outdoor=true&spec_resolution=2mp&sort=price_asc&page=2");
  assert.match(discoveryPageHref("/search", query, apiPath("/api/v1/catalog/products/?page=3")), /spec_resolution=2mp.*page=3$/);
  assert.equal(discoveryHref("/search", withoutFilters(query)), "/search?q=DS-2CE&sort=price_asc");
  const changed = withCategory(query, "storage");
  assert.equal(changed.q, "DS-2CE");
  assert.equal(changed.category, "storage");
  assert.equal(changed.brand, "");
  assert.deepEqual(changed.specifications, {});
  assert.equal(changed.page, 1);
  assert.equal(discoveryHref("/search", changed), "/search?q=DS-2CE&category=storage&sort=price_asc");
});

test("validates known technical types and ranges without rejecting unobserved active values", () => {
  for (const [search, field] of [
    ["spec_outdoor=maybe", "spec_outdoor"],
    ["spec_ir_distance_min=25&spec_ir_distance_max=20", "spec_ir_distance_max"],
    ["spec_ir_distance_min=2.12345", "spec_ir_distance_min"],
  ]) {
    const query = parseDiscoveryQuery(new URLSearchParams(`category=cameras&${search}`)).query;
    assert.ok(validateTechnicalFilters(query, cameraSpecifications)[field], `${search} should fail at ${field}`);
  }
  const storageQuery = parseDiscoveryQuery(new URLSearchParams("category=storage&spec_resolution=2mp")).query;
  assert.deepEqual(validateTechnicalFilters(storageQuery, [{ key: "capacity", label: "Capacity", type: "integer_range", unit: "TB", min: "1", max: "4" }]), {});
  assert.deepEqual(validateTechnicalFilters(parseDiscoveryQuery(new URLSearchParams("category=cameras&spec_resolution=unobserved-active-choice&spec_outdoor=false")).query, cameraSpecifications), {});
  assert.deepEqual(validateTechnicalFilters(parseDiscoveryQuery(new URLSearchParams("category=storage&spec_capacity_min=2&spec_capacity_max=3")).query, [{ key: "capacity", label: "Capacity", type: "integer_range", unit: "TB", min: "1", max: "4" }]), {});
});

test("URL-backed committed state is restored by browser Back", async () => {
  const router = createMemoryRouter([{
    path: "/search",
    loader({ request }) { return parseDiscoveryQuery(new URL(request.url).searchParams).query; },
  }], { initialEntries: ["/search?q=CAM-11&category=cameras&spec_resolution=2mp"] });
  try {
    await router.navigate("/search?q=CAM-11&brand=hikvision&category=cameras&spec_resolution=2mp");
    await router.navigate("/search?q=CAM-11&category=storage&spec_capacity_min=2&sort=price_asc");
    await router.navigate(-1);
    assert.equal(router.state.location.search, "?q=CAM-11&brand=hikvision&category=cameras&spec_resolution=2mp");
    assert.deepEqual(router.state.loaderData["0"], parseDiscoveryQuery(new URLSearchParams("q=CAM-11&brand=hikvision&category=cameras&spec_resolution=2mp")).query);
  } finally {
    router.dispose();
  }
});
