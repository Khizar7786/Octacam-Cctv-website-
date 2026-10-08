import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { hasValidSale, type PublicProduct } from "~/features/catalog/api";

function ProductImage({ product }: { product: PublicProduct }) {
  const [failedUrls, setFailedUrls] = useState<string[]>([]);
  const [readyUrl, setReadyUrl] = useState<string | null>(null);
  const previewRef = useRef<HTMLImageElement>(null);
  const primary = product.primary_image && !failedUrls.includes(product.primary_image.image_url) ? product.primary_image : null;
  const secondary = product.secondary_image && !failedUrls.includes(product.secondary_image.image_url) ? product.secondary_image : null;
  const image = primary ?? secondary;
  const preview = primary && secondary && primary.image_url !== secondary.image_url ? secondary : null;

  // A cached image can finish before hydration attaches its load handler.
  useEffect(() => {
    if (previewRef.current?.complete && previewRef.current.naturalWidth > 0) setReadyUrl(preview?.image_url ?? null);
  }, [preview?.image_url]);

  function markFailed(url: string) {
    setFailedUrls((current) => [...current, url]);
  }

  return (
    <div className="product-card-media">
      {image ? (
        <img
          alt={image.alt_text || product.name}
          className="h-full w-full object-contain"
          height={image.height}
          loading="lazy"
          onError={() => markFailed(image.image_url)}
          src={image.image_url}
          width={image.width}
        />
      ) : <span>Image unavailable</span>}
      {preview ? (
        <img
          alt=""
          aria-hidden="true"
          className="product-card-secondary"
          data-ready={readyUrl === preview.image_url}
          height={preview.height}
          loading="lazy"
          onError={() => markFailed(preview.image_url)}
          onLoad={() => setReadyUrl(preview.image_url)}
          ref={previewRef}
          src={preview.image_url}
          width={preview.width}
        />
      ) : null}
      {hasValidSale(product) ? <span className="product-sale-badge">Sale</span> : null}
    </div>
  );
}

export function ProductCard({ product }: { product: PublicProduct }) {
  const hasSale = hasValidSale(product);

  return (
    <article className="product-card">
      <Link aria-labelledby={`product-card-title-${product.id}`} className="product-card-link" to={`/products/${encodeURIComponent(product.slug)}`}>
        <ProductImage product={product} />
        <div className="product-card-copy">
          <h3 className="product-card-title" id={`product-card-title-${product.id}`}>{product.name}</h3>
          <div className="mt-auto flex min-h-7 flex-wrap items-center justify-center gap-x-2 gap-y-0.5 pt-2">
            {hasSale ? <p className="text-xs text-muted-foreground"><span className="sr-only">Regular price: </span><s>PKR {product.regular_price}</s></p> : null}
            <p className="text-base font-bold text-navigation">PKR {product.selling_price}</p>
          </div>
        </div>
      </Link>
    </article>
  );
}
