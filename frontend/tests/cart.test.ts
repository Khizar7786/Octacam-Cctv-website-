import assert from "node:assert/strict";
import { test } from "node:test";
import { createApiClient } from "../app/lib/api/client.ts";
import { resolveCartProducts } from "../app/features/cart/resolve.ts";
import {
  CART_STORAGE_KEY, cartCount, cartReducer, formatPkr, initialCartState, lineTotal,
  parseStoredCart, serializeCart,
} from "../app/features/cart/state.ts";

const product = (id: number, stock_quantity: number, selling_price = "7499.00") => ({
  id, brand: { id: 1, name: "Hikvision", slug: "hikvision" },
  category: { id: 2, name: "Cameras", slug: "cameras" },
  sku: `DS-${id}`, slug: `ds-${id}`, name: `Camera ${id}`, short_description: "",
  regular_price: selling_price, sale_price: null, selling_price, stock_quantity,
  is_in_stock: stock_quantity > 0, primary_image: null, secondary_image: null,
});

test("recovers malformed browser storage and persists only IDs and quantities", () => {
  assert.equal(CART_STORAGE_KEY, "octacam.cart.v1");
  assert.deepEqual(parseStoredCart("{bad"), { items: [], recovered: true });
  assert.deepEqual(parseStoredCart('{"product_id":7}'), { items: [], recovered: true });
  const recovered = parseStoredCart(JSON.stringify([
    { product_id: 7, quantity: 2, price: "0.01", stock: 99 },
    { product_id: 7, quantity: 1 },
    { product_id: -1, quantity: 3 },
    { product_id: 8, quantity: "4" },
  ]));
  assert.deepEqual(recovered, { items: [{ product_id: 7, quantity: 3 }], recovered: true });
  assert.equal(serializeCart(recovered.items), '[{"product_id":7,"quantity":3}]');
});

test("cart reducer restores on reload and caps additions to known stock", () => {
  const added = cartReducer(
    cartReducer(initialCartState, { type: "hydrate", items: [], storageWarning: null }),
    { type: "add", productId: 7, quantity: 2, available: 3 },
  );
  const capped = cartReducer(added, { type: "add", productId: 7, quantity: 2, available: 3 });
  assert.deepEqual(capped.items, [{ product_id: 7, quantity: 3 }]);
  assert.equal(cartCount(capped.items), 3);
  const reloaded = cartReducer(initialCartState, { type: "hydrate", ...{ items: parseStoredCart(serializeCart(capped.items)).items, storageWarning: null } });
  assert.deepEqual(reloaded.items, capped.items);
  assert.deepEqual(cartReducer(reloaded, { type: "remove", productId: 7 }).items, []);
});

test("stock reductions require a smaller quantity and decimal subtotal stays exact", () => {
  const restored = cartReducer(initialCartState, { type: "hydrate", items: [{ product_id: 7, quantity: 3 }], storageWarning: null });
  const reduced = cartReducer(restored, { type: "setQuantity", productId: 7, quantity: 3, available: 1 });
  assert.deepEqual(reduced.items, [{ product_id: 7, quantity: 1 }]);
  assert.equal(formatPkr(lineTotal("7499.00", reduced.items[0].quantity)), "PKR 7,499.00");
  assert.equal(formatPkr(lineTotal("0.10", 3)), "PKR 0.30");
  assert.deepEqual(cartReducer(reduced, { type: "setQuantity", productId: 7, quantity: 1, available: 0 }).items, reduced.items);
});

test("cart resolves IDs through paginated public contract and leaves unpublished IDs unresolved", async () => {
  const requested: string[] = [];
  const client = createApiClient({ fetch: async (input) => {
    requested.push(String(input));
    const second = String(input).includes("page=2");
    return Response.json({
      count: 3, next: second ? null : "http://backend-internal:8000/api/v1/catalog/products/?page=2",
      previous: null, results: second ? [product(8, 0)] : [product(7, 1)],
    });
  } });
  const resolved = await resolveCartProducts(client, [7, 8, 99]);
  assert.deepEqual([...resolved.keys()], [7, 8]);
  assert.equal(resolved.get(7)?.stock_quantity, 1);
  assert.equal(resolved.get(8)?.stock_quantity, 0);
  assert.deepEqual(requested, ["/api/v1/catalog/products/", "/api/v1/catalog/products/?page=2"]);
});
