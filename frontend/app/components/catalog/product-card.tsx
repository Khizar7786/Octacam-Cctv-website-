import { useState } from "react";
import { Link } from "react-router";
import type { Money, PublicProduct } from "~/features/catalog/api";

function isLowerPrice(value: Money, regular: Money): boolean {
  return BigInt(value.replace(".", "")) < BigInt(regular.replace(".", ""));
}

function ProductImage({ product }: { product: PublicProduct }) {
  const [failed, setFailed] = useState(false);
  const image = product.primary_image;

  return (
    <div className="flex aspect-[4/3] items-center justify-center overflow-hidden rounded-md bg-muted text-sm font-semibold text-muted-foreground">
      {image && !failed ? (
        <img
          alt={image.alt_text || product.name}
          className="h-full w-full object-contain"
          height={image.height}
          loading="lazy"
          onError={() => setFailed(true)}
          src={image.image_url}
          width={image.width}
        />
      ) : <span>Image unavailable</span>}
    </div>
  );
}

export function ProductCard({ product }: { product: PublicProduct }) {
  const hasSale = product.sale_price !== null
    && product.sale_price === product.selling_price
    && isLowerPrice(product.sale_price, product.regular_price);

  return (
    <article className="flex min-w-0 flex-col rounded-lg border border-border bg-card p-4 shadow-sm">
      <ProductImage product={product} />
      <p className="mt-4 text-xs font-semibold text-muted-foreground">{product.brand.name} · {product.category.name}</p>
      <h3 className="mt-1 text-base font-bold leading-snug">{product.name}</h3>
      <p className="mt-1 break-all font-mono text-xs text-muted-foreground">Model/SKU: {product.sku}</p>
      <div className="mt-auto pt-4">
        <p className="text-lg font-bold">PKR {product.selling_price}</p>
        {hasSale ? <p className="text-sm text-muted-foreground">Regular price: <s>PKR {product.regular_price}</s></p> : null}
        <p className="mt-2 text-sm font-semibold">{product.is_in_stock ? "In stock" : "Out of stock"}</p>
        <Link className="mt-3 inline-flex min-h-11 items-center text-sm" to={`/products/${encodeURIComponent(product.slug)}`}>
          Product details <span className="ml-1 text-xs font-normal">(coming soon)</span>
        </Link>
      </div>
    </article>
  );
}
