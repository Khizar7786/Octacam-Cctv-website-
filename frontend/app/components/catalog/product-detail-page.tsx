import { useEffect, useRef, useState } from "react";
import { Link, useRevalidator } from "react-router";
import { Breadcrumbs } from "./catalog-listing";
import { buttonStyles } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { contact } from "~/config/storefront";
import { hasValidSale, type ProductImage, type PublicProductDetail } from "~/features/catalog/api";
import { clampQuantity } from "~/features/catalog/product";

function ProductGallery({ product }: { product: PublicProductDetail }) {
  const [selected, setSelected] = useState(0);
  const [failedMainUrl, setFailedMainUrl] = useState<string | null>(null);
  const [failedThumbnails, setFailedThumbnails] = useState<string[]>([]);
  const images = product.images;
  const selectedIndex = Math.min(selected, Math.max(images.length - 1, 0));
  const image = images[selectedIndex];
  const imageLabel = (item: ProductImage, index: number) => item.alt_text.trim() || `${product.name}, image ${index + 1}`;

  return (
    <section aria-label="Product images" className="min-w-0">
      <figure>
        <div className="flex aspect-[4/3] items-center justify-center overflow-hidden rounded-lg border border-border bg-muted text-sm font-semibold text-muted-foreground">
          {image && failedMainUrl !== image.image_url ? (
            <img alt={imageLabel(image, selectedIndex)} className="h-full w-full object-contain" height={image.height} onError={() => setFailedMainUrl(image.image_url)} src={image.image_url} width={image.width} />
          ) : <span>Image unavailable</span>}
        </div>
        {images.length > 1 ? <figcaption className="mt-2 text-sm text-muted-foreground">Image {selectedIndex + 1} of {images.length}</figcaption> : null}
      </figure>
      {images.length > 1 ? (
        <div aria-label="Choose a product image" className="mt-4 flex flex-wrap gap-3" role="group">
          {images.map((item, index) => (
            <button
              aria-label={`View image ${index + 1}: ${imageLabel(item, index)}`}
              aria-pressed={selectedIndex === index}
              className={`flex size-20 items-center justify-center overflow-hidden rounded-md border bg-muted text-xs text-muted-foreground ${selectedIndex === index ? "border-primary ring-2 ring-primary" : "border-border-strong"}`}
              key={item.id}
              onClick={() => setSelected(index)}
              type="button"
            >
              {failedThumbnails.includes(item.image_url) ? <span>Image unavailable</span> : (
                <img alt="" className="h-full w-full object-contain" height={item.height} loading="lazy" onError={() => setFailedThumbnails((current) => [...current, item.image_url])} src={item.image_url} width={item.width} />
              )}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function PurchasePanel({ product }: { product: PublicProductDetail }) {
  const [quantity, setQuantity] = useState("1");
  const [updateNotice, setUpdateNotice] = useState("");
  const previous = useRef({ stock: product.stock_quantity, price: product.selling_price });
  const revalidator = useRevalidator();
  const available = product.stock_quantity > 0;

  useEffect(() => {
    if (previous.current.stock === product.stock_quantity && previous.current.price === product.selling_price) return;
    setQuantity((current) => String(clampQuantity(current, product.stock_quantity)));
    setUpdateNotice("Price or availability changed. Review the current product details.");
    previous.current = { stock: product.stock_quantity, price: product.selling_price };
  }, [product.stock_quantity, product.selling_price]);

  return (
    <section aria-labelledby="purchase-heading" className="min-w-0 rounded-lg border border-border bg-card p-5 shadow-sm sm:p-6">
      <h2 className="text-lg font-bold" id="purchase-heading">Price and availability</h2>
      <p className="mt-3 text-3xl font-bold leading-tight">PKR {product.selling_price}</p>
      {hasValidSale(product) ? <p className="mt-1 text-sm text-muted-foreground">Regular price: <s>PKR {product.regular_price}</s></p> : null}
      <p className={`mt-4 font-semibold ${available ? "text-success" : "text-error"}`} role="status">
        {available ? `In stock · ${product.stock_quantity} available when checked` : "Out of stock"}
      </p>
      {updateNotice ? <p className="mt-3 rounded-md border border-info bg-info-surface p-3 text-sm" role="status">{updateNotice}</p> : null}
      {available ? (
        <div className="mt-5 max-w-36">
          <label className="mb-1 block text-sm font-semibold" htmlFor="product-quantity">Quantity</label>
          <Input id="product-quantity" inputMode="numeric" max={product.stock_quantity} min={1} onBlur={() => setQuantity(String(clampQuantity(quantity, product.stock_quantity)))} onChange={(event) => setQuantity(event.target.value === "" ? "" : String(clampQuantity(event.target.value, product.stock_quantity)))} step={1} type="number" value={quantity} />
          <p className="mt-1 text-xs text-muted-foreground">Maximum currently available: {product.stock_quantity}</p>
        </div>
      ) : <p className="mt-3 text-sm">This product cannot be purchased while it is out of stock.</p>}
      <button className={buttonStyles({ className: "mt-5 w-full" })} disabled type="button">{available ? "Add to cart (coming soon)" : "Out of stock"}</button>
      {available ? <p className="mt-2 text-sm text-muted-foreground">The cart is being built. Selecting a quantity does not add or reserve this item.</p> : null}
      <button className={buttonStyles({ variant: "outline", className: "mt-5 w-full" })} disabled={revalidator.state === "loading"} onClick={() => revalidator.revalidate()} type="button">
        {revalidator.state === "loading" ? "Checking availability…" : "Refresh price and stock"}
      </button>
      <div className="mt-6 border-t border-border pt-4 text-sm">
        <p>Equipment checkout will use cash on delivery. <Link to="/shipping">Shipping policy (coming soon)</Link></p>
        <p className="mt-2 text-muted-foreground">Final shipping and tax amounts will be shown by checkout when it is available.</p>
      </div>
    </section>
  );
}

export function ProductDetailPage({ product }: { product: PublicProductDetail }) {
  const channels = [
    { label: "WhatsApp", value: contact.whatsapp },
    { label: "Phone", value: contact.phone },
    { label: "Email", value: contact.email },
  ].filter((channel) => channel.value !== null);

  return (
    <article className="space-y-8">
      <Breadcrumbs items={[
        { label: "Home", to: "/" },
        { label: "Shop", to: "/shop" },
        { label: product.category.name, to: `/categories/${encodeURIComponent(product.category.slug)}` },
        { label: product.name },
      ]} />
      <header className="max-w-3xl">
        <p className="text-sm font-bold text-primary"><Link to={`/brands/${encodeURIComponent(product.brand.slug)}`}>{product.brand.name}</Link> · {product.category.name}</p>
        <h1 className="mt-2 text-[length:var(--font-size-heading)] font-bold leading-tight">{product.name}</h1>
        <p className="mt-2 break-all font-mono text-sm text-muted-foreground">Model/SKU: {product.sku}</p>
        {product.short_description.trim() ? <p className="mt-4 max-w-[var(--reading-max)] text-base">{product.short_description}</p> : null}
      </header>

      <div className="grid gap-7 lg:grid-cols-[minmax(19rem,0.8fr)_minmax(0,1.2fr)] lg:items-start">
        <PurchasePanel product={product} />
        <ProductGallery product={product} />
      </div>

      <div className="grid gap-8 border-t border-border pt-8 lg:grid-cols-[minmax(0,1.2fr)_minmax(19rem,0.8fr)]">
        <div className="space-y-8">
          {product.full_description.trim() ? (
            <section aria-labelledby="description-heading">
              <h2 className="text-xl font-bold" id="description-heading">Product overview</h2>
              <p className="mt-3 max-w-[var(--reading-max)] whitespace-pre-line">{product.full_description}</p>
            </section>
          ) : null}
          {product.specifications.length ? (
            <section aria-labelledby="specifications-heading">
              <h2 className="text-xl font-bold" id="specifications-heading">Technical specifications</h2>
              <dl className="mt-4 overflow-hidden rounded-lg border border-border bg-card">
                {product.specifications.map((specification) => (
                  <div className="grid gap-1 border-b border-border px-4 py-3 last:border-b-0 sm:grid-cols-[minmax(0,12rem)_minmax(0,1fr)] sm:gap-4" key={specification.definition}>
                    <dt className="text-sm font-semibold text-muted-foreground">{specification.label}</dt>
                    <dd className="min-w-0 break-words text-sm font-medium">{specification.display_value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}
        </div>
        <div className="space-y-6">
          <section aria-labelledby="warranty-heading" className="rounded-lg border border-border bg-card p-5">
            <h2 className="text-lg font-bold" id="warranty-heading">Warranty information</h2>
            <p className="mt-2 whitespace-pre-line text-sm">{product.warranty_text.trim() || "Product-specific warranty terms have not been provided."}</p>
            <p className="mt-3 text-sm"><Link to="/warranty">Warranty policy (coming soon)</Link></p>
          </section>
          <section aria-labelledby="support-heading" className="rounded-lg border border-border bg-card p-5">
            <h2 className="text-lg font-bold" id="support-heading">Questions about this product?</h2>
            {channels.length ? (
              <ul className="mt-3 space-y-2 text-sm">
                {channels.map(({ label, value }) => value ? <li key={label}><a href={value.href}>{label}: {value.display}</a></li> : null)}
              </ul>
            ) : <p className="mt-2 text-sm text-muted-foreground">Support contact details are pending verification.</p>}
            <p className="mt-3 text-sm"><Link to="/contact">Contact page (coming soon)</Link></p>
          </section>
          <section className="rounded-lg border border-info bg-info-surface p-5 text-sm">
            <h2 className="text-lg font-bold">Planning a Lahore installation?</h2>
            <p className="mt-2">A site survey is free in Lahore. Installation is quoted and scheduled separately afterward.</p>
            <p className="mt-3"><Link to="/surveys">Site survey booking (coming soon)</Link></p>
          </section>
        </div>
      </div>
    </article>
  );
}
