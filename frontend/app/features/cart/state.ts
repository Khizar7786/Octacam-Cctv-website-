export const CART_STORAGE_KEY = "octacam.cart.v1";
export const MAX_CART_QUANTITY = 2_147_483_647;

export interface CartItem {
  product_id: number;
  quantity: number;
}

export interface CartState {
  items: CartItem[];
  ready: boolean;
  storageWarning: string | null;
}

export type CartAction =
  | { type: "hydrate"; items: CartItem[]; storageWarning: string | null }
  | { type: "add"; productId: number; quantity: number; available: number }
  | { type: "setQuantity"; productId: number; quantity: number; available: number }
  | { type: "remove"; productId: number }
  | { type: "storageError" };

export const initialCartState: CartState = { items: [], ready: false, storageWarning: null };

function validId(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) > 0;
}

function validQuantity(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) > 0 && (value as number) <= MAX_CART_QUANTITY;
}

/** Invalid rows are discarded so one damaged entry cannot hide the rest of a cart. */
export function parseStoredCart(raw: string | null): { items: CartItem[]; recovered: boolean } {
  if (raw === null) return { items: [], recovered: false };
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { items: [], recovered: true };
  }
  if (!Array.isArray(parsed)) return { items: [], recovered: true };
  const quantities = new Map<number, number>();
  let recovered = false;
  for (const row of parsed) {
    if (typeof row !== "object" || row === null || Array.isArray(row)
      || !validId((row as Record<string, unknown>).product_id) || !validQuantity((row as Record<string, unknown>).quantity)) {
      recovered = true;
      continue;
    }
    const item = row as CartItem;
    if (Object.keys(row).some((key) => key !== "product_id" && key !== "quantity")) recovered = true;
    const previous = quantities.get(item.product_id) ?? 0;
    if (previous) recovered = true;
    quantities.set(item.product_id, Math.min(MAX_CART_QUANTITY, previous + item.quantity));
  }
  return { items: [...quantities].map(([product_id, quantity]) => ({ product_id, quantity })), recovered };
}

export function serializeCart(items: CartItem[]): string {
  return JSON.stringify(items.map(({ product_id, quantity }) => ({ product_id, quantity })));
}

export function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case "hydrate":
      return { items: action.items, ready: true, storageWarning: action.storageWarning };
    case "storageError":
      return { ...state, storageWarning: "Browser storage is unavailable. Cart changes may not survive a reload." };
    case "add": {
      if (!validId(action.productId) || !validQuantity(action.quantity) || !validQuantity(action.available)) return state;
      const current = state.items.find((item) => item.product_id === action.productId);
      const quantity = Math.min(action.available, (current?.quantity ?? 0) + action.quantity);
      if (current?.quantity === quantity) return state;
      return {
        ...state,
        items: current
          ? state.items.map((item) => item.product_id === action.productId ? { ...item, quantity } : item)
          : [...state.items, { product_id: action.productId, quantity }],
      };
    }
    case "setQuantity": {
      if (!validId(action.productId) || !validQuantity(action.quantity) || !validQuantity(action.available)) return state;
      return { ...state, items: state.items.map((item) => item.product_id === action.productId
        ? { ...item, quantity: Math.min(action.quantity, action.available) } : item) };
    }
    case "remove":
      return { ...state, items: state.items.filter((item) => item.product_id !== action.productId) };
  }
}

export function cartCount(items: CartItem[]): number {
  return items.reduce((count, item) => count + item.quantity, 0);
}

export function lineTotal(price: string, quantity: number): bigint {
  return BigInt(price.replace(".", "")) * BigInt(quantity);
}

export function formatPkr(cents: bigint): string {
  const units = cents / 100n;
  return `PKR ${units.toLocaleString("en-PK")}.${(cents % 100n).toString().padStart(2, "0")}`;
}
