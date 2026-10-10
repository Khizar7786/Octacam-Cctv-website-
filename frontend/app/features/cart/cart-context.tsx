import { createContext, useContext, useEffect, useReducer, type Dispatch, type ReactNode } from "react";
import {
  CART_STORAGE_KEY, cartReducer, initialCartState, parseStoredCart, serializeCart,
  type CartAction, type CartState,
} from "./state";

interface CartContextValue {
  state: CartState;
  dispatch: Dispatch<CartAction>;
}

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(cartReducer, initialCartState);

  useEffect(() => {
    try {
      const { items, recovered } = parseStoredCart(window.localStorage.getItem(CART_STORAGE_KEY));
      dispatch({ type: "hydrate", items, storageWarning: recovered ? "Some saved cart data was invalid and has been removed." : null });
    } catch {
      dispatch({ type: "hydrate", items: [], storageWarning: "Browser storage is unavailable. Cart changes may not survive a reload." });
    }
  }, []);

  useEffect(() => {
    if (!state.ready) return;
    try {
      window.localStorage.setItem(CART_STORAGE_KEY, serializeCart(state.items));
    } catch {
      if (!state.storageWarning) dispatch({ type: "storageError" });
    }
  }, [state.items, state.ready, state.storageWarning]);

  return <CartContext.Provider value={{ state, dispatch }}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const cart = useContext(CartContext);
  if (!cart) throw new Error("CartProvider is required for cart controls.");
  return cart;
}
