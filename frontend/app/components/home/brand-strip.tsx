import { useState } from "react";
import { Link } from "react-router";
import { StoreIcon } from "~/components/ui/store-icon";
import { useBrandStrip } from "./use-brand-strip";
import "~/styles/home.css";

interface BrandEntry {
  id: number;
  name: string;
  slug: string;
  logoUrl: string | null;
}

function BrandLogo({ brand, duplicate = false }: { brand: BrandEntry; duplicate?: boolean }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  return (
    <li>
      <Link aria-label={`Browse ${brand.name} products`} className="brand-strip-link" tabIndex={duplicate ? -1 : undefined} title={brand.name} to={`/brands/${encodeURIComponent(brand.slug)}`}>
        {brand.logoUrl && failedUrl !== brand.logoUrl ? (
          <img alt={`${brand.name} logo`} decoding="async" height={48} onError={() => setFailedUrl(brand.logoUrl)} src={brand.logoUrl} width={128} />
        ) : <span>{brand.name}</span>}
      </Link>
    </li>
  );
}

export function BrandStrip({ brands, unavailable = false }: { brands: BrandEntry[]; unavailable?: boolean }) {
  const strip = useBrandStrip(brands.length);

  return (
    <section aria-labelledby="brands-heading" className="brand-strip" data-animated={strip.enabled} id="brands"
      onPointerEnter={(event) => { if (event.pointerType === "mouse") strip.setHovered(true); }}
      onPointerLeave={(event) => { if (event.pointerType === "mouse") strip.setHovered(false); }}>
      <div className="brand-strip-heading">
        <h2 id="brands-heading">Shop by Brands</h2>
        <Link className="brand-strip-all" to="/brands">All brands <StoreIcon name="next" /></Link>
      </div>
      {brands.length > 0 ? (
        <>
          <p className="sr-only" id="brand-strip-help">Scroll or swipe to browse brands. Automatic scrolling pauses while you hover the section or focus the logos and resumes when you leave.</p>
          <div aria-describedby="brand-strip-help" aria-label="Brand logos" className="brand-strip-viewport" id="brand-logo-viewport"
            onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) strip.setFocused(false); }}
            onFocusCapture={() => strip.setFocused(true)}
            ref={strip.viewportRef} role="region" tabIndex={0}>
            <div className="brand-strip-track">
              <ul className="brand-strip-group" ref={strip.groupRef}>
                {brands.map((brand) => <BrandLogo brand={brand} key={brand.id} />)}
              </ul>
              {/* Copies close the loop visually; the original list is the keyboard/AT route. */}
              {Array.from({ length: strip.copies }, (_, index) => (
                <ul aria-hidden="true" className="brand-strip-group brand-strip-copy" key={index}>
                  {brands.map((brand) => <BrandLogo brand={brand} duplicate key={brand.id} />)}
                </ul>
              ))}
            </div>
          </div>
        </>
      ) : <p className="brand-strip-empty" role="status">{unavailable ? "Brand information is unavailable right now." : "No active brands are available yet."}</p>}
    </section>
  );
}
