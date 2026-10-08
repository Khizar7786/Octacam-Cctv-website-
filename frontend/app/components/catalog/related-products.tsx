import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ProductCard } from "./product-card";
import { StoreIcon } from "~/components/ui/store-icon";
import type { PublicProduct } from "~/features/catalog/api";

export function RelatedProducts({ products, category }: { products: PublicProduct[]; category: PublicProduct["category"] }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ previous: false, next: false });

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    function updateEdges() {
      const maximum = track!.scrollWidth - track!.clientWidth;
      const next = { previous: track!.scrollLeft > 2, next: track!.scrollLeft < maximum - 2 };
      setEdges((current) => current.previous === next.previous && current.next === next.next ? current : next);
    }
    updateEdges();
    const observer = new ResizeObserver(updateEdges);
    observer.observe(track);
    track.addEventListener("scroll", updateEdges, { passive: true });
    return () => {
      observer.disconnect();
      track.removeEventListener("scroll", updateEdges);
    };
  }, [products]);

  function move(direction: number) {
    const track = trackRef.current;
    if (!track) return;
    track.scrollBy({ left: direction * track.clientWidth, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }

  if (!products.length) return null;
  return (
    <section aria-labelledby="related-products-heading" aria-roledescription="carousel" className="product-related">
      <div className="product-related-heading">
        <div>
          <h2 id="related-products-heading">Related products</h2>
          <Link className="product-text-link" to={`/categories/${encodeURIComponent(category.slug)}`}>View all {category.name}</Link>
        </div>
        {products.length > 1 ? (
          <div className="flex gap-2">
            <button aria-controls="related-products-track" aria-label="Previous related products" className="product-icon-button" disabled={!edges.previous} onClick={() => move(-1)} type="button"><StoreIcon inheritColor name="previous" /></button>
            <button aria-controls="related-products-track" aria-label="Next related products" className="product-icon-button" disabled={!edges.next} onClick={() => move(1)} type="button"><StoreIcon inheritColor name="next" /></button>
          </div>
        ) : null}
      </div>
      <div className="product-related-track" id="related-products-track" ref={trackRef}>
        {products.map((product) => <ProductCard key={product.id} product={product} />)}
      </div>
    </section>
  );
}
