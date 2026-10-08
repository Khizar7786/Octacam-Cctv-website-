import { useEffect, useRef, useState } from "react";
import { Link, useRevalidator } from "react-router";
import { Breadcrumbs } from "./catalog-listing";
import { ProductGallery } from "./product-gallery";
import { RelatedProducts } from "./related-products";
import { buttonStyles } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { StoreIcon, type StoreIconName } from "~/components/ui/store-icon";
import { contact } from "~/config/storefront";
import { hasValidSale, type PublicProduct, type PublicProductDetail } from "~/features/catalog/api";
import { clampQuantity } from "~/features/catalog/product";

function ProductBrand({ product, logoUrl }: { product: PublicProductDetail; logoUrl: string | null }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  return (
    <Link aria-label={`${product.brand.name} products`} className="product-brand" to={`/brands/${encodeURIComponent(product.brand.slug)}`}>
      {logoUrl && failedUrl !== logoUrl ? <img alt={`${product.brand.name} logo`} onError={() => setFailedUrl(logoUrl)} src={logoUrl} /> : <span>{product.brand.name}</span>}
    </Link>
  );
}

function PurchasePanel({ product }: { product: PublicProductDetail }) {
  const [quantity, setQuantity] = useState("1");
  const [updateNotice, setUpdateNotice] = useState("");
  const previous = useRef({ stock: product.stock_quantity, price: product.selling_price });
  const revalidator = useRevalidator();
  const available = product.stock_quantity > 0;
  const amount = clampQuantity(quantity, product.stock_quantity);

  useEffect(() => {
    if (previous.current.stock === product.stock_quantity && previous.current.price === product.selling_price) return;
    setQuantity((current) => String(clampQuantity(current, product.stock_quantity)));
    setUpdateNotice("Price or availability changed. Review the current product details.");
    previous.current = { stock: product.stock_quantity, price: product.selling_price };
  }, [product.stock_quantity, product.selling_price]);

  return (
    <section aria-label="Price and availability" className="product-purchase">
      <div className="product-detail-price">
        <p>PKR {product.selling_price}</p>
        {hasValidSale(product) ? <><s><span className="sr-only">Regular price: </span>PKR {product.regular_price}</s><span className="product-detail-sale">Sale</span></> : null}
      </div>
      <p className={`product-stock ${available ? "text-success" : "text-error"}`} role="status">
        <span aria-hidden="true" className="product-stock-dot" />
        {available ? `In stock · ${product.stock_quantity} available when checked` : "Out of stock"}
      </p>
      {updateNotice ? <p className="mt-3 rounded-md border border-info bg-info-surface p-3 text-sm" role="status">{updateNotice}</p> : null}
      <div className="product-purchase-actions">
        {available ? (
          <div>
            <label className="product-quantity-label" htmlFor="product-quantity">Quantity</label>
            <div className="product-quantity">
              <button aria-label="Decrease quantity" disabled={amount <= 1} onClick={() => setQuantity(String(clampQuantity(String(amount - 1), product.stock_quantity)))} type="button"><StoreIcon inheritColor name="minus" /></button>
              <Input id="product-quantity" inputMode="numeric" max={product.stock_quantity} min={1} onBlur={() => setQuantity(String(clampQuantity(quantity, product.stock_quantity)))} onChange={(event) => setQuantity(event.target.value === "" ? "" : String(clampQuantity(event.target.value, product.stock_quantity)))} step={1} type="number" value={quantity} />
              <button aria-label="Increase quantity" disabled={amount >= product.stock_quantity} onClick={() => setQuantity(String(clampQuantity(String(amount + 1), product.stock_quantity)))} type="button"><StoreIcon inheritColor name="plus" /></button>
            </div>
          </div>
        ) : null}
        <button className={buttonStyles({ className: "product-cart-action" })} disabled type="button">{available ? "Add to cart (coming soon)" : "Out of stock"}</button>
      </div>
      <p className="product-purchase-note">{available ? "The cart is being built. Selecting a quantity does not add or reserve this item." : "This product cannot be purchased while it is out of stock."}</p>
      <button className="product-refresh" disabled={revalidator.state === "loading"} onClick={() => revalidator.revalidate()} type="button">
        <StoreIcon name="refresh" />{revalidator.state === "loading" ? "Checking availability…" : "Refresh price and stock"}
      </button>
      <div className="product-delivery-note">
        <StoreIcon badge name="cart" />
        <div><p className="font-semibold">Cash on delivery for equipment checkout</p><p>Final shipping and tax amounts will be shown at checkout. <Link to="/shipping">Shipping policy (coming soon)</Link></p></div>
      </div>
    </section>
  );
}

function ProductInformation({ product }: { product: PublicProductDetail }) {
  const description = product.full_description.trim();
  const warranty = product.warranty_text.trim();
  const sections = [
    ...(description ? [{ id: "description", label: "Description" }] : []),
    ...(product.specifications.length ? [{ id: "specifications", label: "Specifications" }] : []),
    ...(warranty ? [{ id: "warranty", label: "Warranty" }] : []),
  ];
  if (!sections.length) return null;

  return (
    <div className="product-information">
      <nav aria-label="Product information" className="product-section-nav">
        {sections.map((section) => <a href={`#product-${section.id}`} key={section.id}>{section.label}</a>)}
      </nav>
      {description ? (
        <section aria-labelledby="description-heading" className="product-information-section" id="product-description">
          <h2 id="description-heading">Product overview</h2>
          <p className="product-description">{description}</p>
        </section>
      ) : null}
      {product.specifications.length ? (
        <section aria-labelledby="specifications-heading" className="product-information-section" id="product-specifications">
          <h2 id="specifications-heading">Technical specifications</h2>
          <dl className="product-specifications">
            {product.specifications.map((specification) => (
              <div key={specification.definition}><dt>{specification.label}</dt><dd>{specification.display_value}</dd></div>
            ))}
          </dl>
        </section>
      ) : null}
      {warranty ? (
        <section aria-labelledby="warranty-heading" className="product-information-section" id="product-warranty">
          <h2 id="warranty-heading">Warranty information</h2>
          <p className="product-description">{warranty}</p>
          <Link className="product-text-link" to="/warranty">Warranty policy (coming soon)</Link>
        </section>
      ) : null}
    </div>
  );
}

export function ProductDetailPage({ product, brandLogoUrl, relatedProducts }: { product: PublicProductDetail; brandLogoUrl: string | null; relatedProducts: PublicProduct[] }) {
  const channels: { label: string; value: typeof contact.whatsapp; icon: StoreIconName }[] = [
    { label: "WhatsApp", value: contact.whatsapp, icon: "whatsapp" },
    { label: "Phone", value: contact.phone, icon: "phone" },
    { label: "Email", value: contact.email, icon: "email" },
  ];
  const verifiedChannels = channels.filter((channel) => channel.value !== null);

  return (
    <article className="product-detail">
      <Breadcrumbs items={[
        { label: "Home", to: "/" },
        { label: "Shop", to: "/shop" },
        { label: product.category.name, to: `/categories/${encodeURIComponent(product.category.slug)}` },
        { label: product.name },
      ]} />
      <div className="product-top">
        <header className="product-identity">
          <div className="product-identity-topline">
            <Link className="product-category" to={`/categories/${encodeURIComponent(product.category.slug)}`}>{product.category.name}</Link>
            <ProductBrand logoUrl={brandLogoUrl} product={product} />
          </div>
          <h1>{product.name}</h1>
          <p className="product-sku">Model/SKU: {product.sku}</p>
        </header>
        <ProductGallery product={product} />
        <div className="product-summary">
          <PurchasePanel product={product} />
          {product.short_description.trim() ? <p className="product-short-description">{product.short_description}</p> : null}
          {product.specifications.length ? <dl aria-label="Key product specifications" className="product-key-specifications">{product.specifications.slice(0, 4).map((specification) => <div key={specification.definition}><dt>{specification.label}</dt><dd>{specification.display_value}</dd></div>)}</dl> : null}
          <div className="product-support">
            {verifiedChannels.length ? <div className="flex flex-wrap gap-x-4 gap-y-1">{verifiedChannels.map(({ label, value, icon }) => value ? <a href={value.href} key={label}><StoreIcon name={icon} />{label}: {value.display}</a> : null)}</div> : null}
            <Link to="/contact"><StoreIcon name="contact" />Questions about this product? Contact page (coming soon)</Link>
          </div>
        </div>
      </div>
      <ProductInformation product={product} />
      <aside className="product-survey">
        <StoreIcon badge name="survey" />
        <div><h2>Free Lahore site survey</h2><p>Installation is quoted and scheduled separately afterward.</p></div>
        <Link className="product-text-link" to="/surveys">Site survey booking (coming soon)</Link>
      </aside>
      <RelatedProducts category={product.category} products={relatedProducts} />
    </article>
  );
}
