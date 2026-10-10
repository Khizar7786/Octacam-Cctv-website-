import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { Button, buttonStyles } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { StoreIcon } from "~/components/ui/store-icon";
import { Breadcrumbs } from "~/components/catalog/catalog-listing";
import { type PublicProduct } from "~/features/catalog/api";
import { useCart } from "~/features/cart/cart-context";
import { cartCount, formatPkr, lineTotal } from "~/features/cart/state";
import { resolveCartProducts } from "~/features/cart/resolve";
import { browserApiClient } from "~/lib/api/browser-client";
import "~/styles/cart.css";

export function meta() {
  return [{ title: "Cart | OctaCam" }, { name: "robots", content: "noindex, nofollow" }];
}

function CartImage({ product }: { product: PublicProduct }) {
  const [failed, setFailed] = useState(false);
  const image = product.primary_image;
  return (
    <div className="cart-image">
      {image && !failed ? <img alt={image.alt_text || product.name} className="h-full w-full object-contain" height={image.height} onError={() => setFailed(true)} src={image.image_url} width={image.width} /> : "Image unavailable"}
    </div>
  );
}

function CartQuantity({ productId, productName, quantity, available, onSet }: { productId: number; productName: string; quantity: number; available: number; onSet: (quantity: number) => void }) {
  const [draft, setDraft] = useState(String(quantity));
  const [error, setError] = useState("");
  useEffect(() => setDraft(String(quantity)), [quantity]);

  function commit() {
    const next = Number(draft);
    if (!Number.isSafeInteger(next) || next < 1 || next > available) {
      setError(`Enter a whole number from 1 to ${available}.`);
      return;
    }
    setError("");
    onSet(next);
  }

  function step(direction: number) {
    const current = Number(draft);
    const next = Math.min(available, Math.max(1, (Number.isSafeInteger(current) ? current : quantity) + direction));
    setDraft(String(next));
    setError("");
    onSet(next);
  }

  return (
    <div className="cart-quantity">
      <label htmlFor={`cart-quantity-${productId}`}>Quantity<span className="sr-only"> for {productName}</span></label>
      <div className="cart-stepper">
        <button aria-label={`Decrease quantity for ${productName}`} disabled={quantity <= 1} onClick={() => step(-1)} type="button"><StoreIcon name="minus" inheritColor /></button>
        <Input aria-describedby={error ? `cart-quantity-error-${productId}` : undefined} aria-invalid={!!error} id={`cart-quantity-${productId}`} inputMode="numeric" max={available} min={1} onBlur={commit} onChange={(event) => { setDraft(event.target.value); setError(""); }} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); commit(); } }} type="number" value={draft} />
        <button aria-label={`Increase quantity for ${productName}`} disabled={quantity >= available} onClick={() => step(1)} type="button"><StoreIcon name="plus" inheritColor /></button>
      </div>
      {error ? <p className="mt-1 text-xs text-error" id={`cart-quantity-error-${productId}`}>{error}</p> : null}
    </div>
  );
}

export default function CartPage() {
  const { state, dispatch } = useCart();
  const [products, setProducts] = useState<Map<number, PublicProduct>>(new Map());
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [refresh, setRefresh] = useState(0);
  const [changes, setChanges] = useState<Map<number, string[]>>(new Map());
  const previousProducts = useRef<Map<number, PublicProduct>>(new Map());
  const ids = state.items.map((item) => item.product_id).join(",");

  useEffect(() => {
    if (!state.ready || !ids) return;
    const controller = new AbortController();
    const wanted = ids.split(",").map(Number);
    setStatus("loading");
    resolveCartProducts(browserApiClient, wanted, controller.signal).then((resolved) => {
      const latestChanges = new Map<number, string[]>();
      for (const [id, product] of resolved) {
        const prior = previousProducts.current.get(id);
        const itemChanges: string[] = [];
        if (prior && prior.selling_price !== product.selling_price) itemChanges.push("Price changed since the last check.");
        if (prior && prior.stock_quantity !== product.stock_quantity) itemChanges.push("Availability changed since the last check.");
        if (itemChanges.length) latestChanges.set(id, itemChanges);
      }
      previousProducts.current = resolved;
      setProducts(resolved);
      setChanges(latestChanges);
      setStatus("ready");
    }).catch((error: unknown) => {
      if (!controller.signal.aborted && !(error instanceof DOMException && error.name === "AbortError")) setStatus("error");
    });
    return () => controller.abort();
  }, [ids, refresh, state.ready]);

  const subtotal = useMemo(() => state.items.reduce((sum, item) => {
    const product = products.get(item.product_id);
    if (!product || item.quantity > product.stock_quantity || product.stock_quantity === 0) return sum;
    return sum + lineTotal(product.selling_price, item.quantity);
  }, 0n), [products, state.items]);
  const needsReview = state.items.some((item) => {
    const product = products.get(item.product_id);
    return !product || item.quantity > product.stock_quantity || product.stock_quantity === 0;
  });
  const count = cartCount(state.items);

  return (
    <section className="cart-page" aria-labelledby="cart-title">
      <header className="cart-heading">
        <Breadcrumbs items={[{ label: "Home", to: "/" }, { label: "Cart" }]} />
        <div className="cart-title-row">
          <h1 id="cart-title">Your cart</h1>
          {state.ready && count > 0 ? <span className="cart-count">{count} {count === 1 ? "item" : "items"}</span> : null}
        </div>
        <p>Stock is not reserved. Prices and availability are checked again at checkout.</p>
      </header>
      {state.storageWarning ? <p className="cart-notice cart-notice-warning" role="alert">{state.storageWarning}</p> : null}
      {!state.ready ? <p className="cart-notice" role="status">Loading saved cart…</p> : state.items.length === 0 ? (
        <div className="cart-empty">
          <div className="cart-empty-icon"><StoreIcon name="cart" /></div>
          <h2>Your cart is empty</h2>
          <p>Browse the catalog to find equipment for your project.</p>
          <Link className={buttonStyles()} to="/shop">Browse products</Link>
        </div>
      ) : (
        <>
          {status === "loading" || status === "idle" ? <p className="cart-notice" role="status">Checking current product prices and stock…</p> : null}
          {status === "error" ? (
            <div className="cart-notice cart-notice-error" role="alert">
              <p>Current cart details could not be loaded. Your saved items are still here.</p>
              <Button className="mt-3" onClick={() => setRefresh((value) => value + 1)} variant="outline">Try again</Button>
            </div>
          ) : null}
          {status === "ready" ? (
            <>
              <div className="cart-layout">
                <ul className="cart-items" aria-label="Cart items">
                  {state.items.map((item) => {
                    const product = products.get(item.product_id);
                    const reduced = !!product && product.stock_quantity > 0 && item.quantity > product.stock_quantity;
                    const unavailable = !product || product.stock_quantity === 0;
                    const itemChanges = changes.get(item.product_id);
                    return (
                      <li className="cart-item" key={item.product_id}>
                        {product ? (
                          <>
                            <div className="cart-product">
                              <Link aria-label={`View ${product.name}`} className="cart-image-link" to={`/products/${encodeURIComponent(product.slug)}`}><CartImage product={product} /></Link>
                              <div className="cart-product-copy">
                                <h2><Link to={`/products/${encodeURIComponent(product.slug)}`}>{product.name}</Link></h2>
                                <p className="cart-model">{product.brand.name} · Model/SKU: {product.sku}</p>
                                {!unavailable && !reduced ? <p className="cart-stock">In stock · {product.stock_quantity} available when checked</p> : null}
                              </div>
                              <p className="cart-unit-price"><span>Unit price</span><strong>{formatPkr(lineTotal(product.selling_price, 1))}</strong></p>
                            </div>
                            {itemChanges ? <p className="cart-notice cart-notice-warning" role="status">{itemChanges.join(" ")} Review this item.</p> : null}
                            {unavailable ? <p className="cart-notice cart-notice-error" role="status">Out of stock. This item is excluded from the subtotal.</p> : reduced ? (
                              <p className="cart-notice cart-notice-warning" role="status">Only {product.stock_quantity} now available; you saved {item.quantity}. Choose the available quantity to continue.</p>
                            ) : null}
                            <div className="cart-item-footer">
                                {reduced ? <Button onClick={() => dispatch({ type: "setQuantity", productId: item.product_id, quantity: product.stock_quantity, available: product.stock_quantity })} variant="outline">Use {product.stock_quantity} available</Button> : unavailable ? <span className="text-sm text-muted-foreground">Saved quantity: {item.quantity}</span> : (
                                  <CartQuantity available={product.stock_quantity} onSet={(quantity) => dispatch({ type: "setQuantity", productId: item.product_id, quantity, available: product.stock_quantity })} productId={item.product_id} productName={product.name} quantity={item.quantity} />
                                )}
                              <Button aria-label={`Remove ${product.name}`} className="cart-remove" onClick={() => dispatch({ type: "remove", productId: item.product_id })} variant="ghost"><StoreIcon name="remove" inheritColor />Remove</Button>
                              {!unavailable && !reduced ? <p className="cart-line-total"><span>Line total</span><strong>{formatPkr(lineTotal(product.selling_price, item.quantity))}</strong></p> : null}
                            </div>
                          </>
                        ) : (
                          <div className="cart-unavailable">
                            <h2 className="font-semibold">Product #{item.product_id} is unavailable</h2>
                            <p className="text-sm text-error">This product is no longer in the public catalog. It is excluded from the subtotal.</p>
                            <Button className="cart-remove" onClick={() => dispatch({ type: "remove", productId: item.product_id })} variant="ghost"><StoreIcon name="remove" inheritColor />Remove</Button>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
                <aside className="cart-summary" aria-label="Cart summary">
                  <h2>Summary</h2>
                  <p className="cart-summary-count">{count} {count === 1 ? "item" : "items"} in your cart</p>
                  <div className="cart-subtotal"><span>Eligible items subtotal</span><strong aria-live="polite" aria-atomic="true">{formatPkr(subtotal)}</strong></div>
                  {needsReview ? <p className="cart-notice cart-notice-warning" role="status">Some items need review and are excluded from this subtotal.</p> : null}
                  <dl className="cart-summary-details"><div><dt>Shipping &amp; tax</dt><dd>Calculated at checkout</dd></div></dl>
                  <p className="cart-summary-note">Shipping and tax are not included in this subtotal. Review the final itemized total at checkout.</p>
                  <Link className="cart-policy" to="/shipping">Shipping policy (coming soon)</Link>
                  <div className="cart-checkout-status"><StoreIcon name="cart" /><p>Checkout is being built.<span>No order has been placed.</span></p></div>
                  <Button className="cart-refresh" onClick={() => setRefresh((value) => value + 1)}><StoreIcon name="refresh" inheritColor />Refresh prices and stock</Button>
                  <Link className="cart-continue" to="/shop"><StoreIcon name="previous" />Continue shopping</Link>
                </aside>
              </div>
            </>
          ) : null}
        </>
      )}
    </section>
  );
}
