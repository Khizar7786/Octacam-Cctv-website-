import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { StoreIcon } from "~/components/ui/store-icon";
import type { ProductImage, PublicProductDetail } from "~/features/catalog/api";
import { galleryImageIndex } from "~/features/catalog/product";

function revealThumbnail(rail: HTMLDivElement | null, index: number, focus = false) {
  const button = rail?.querySelector<HTMLButtonElement>(`[data-image-index="${index}"]`);
  if (!rail || !button) return;
  if (focus) button.focus({ preventScroll: true });
  // Scroll just the thumbnail rail, so selecting an image never moves the page.
  if (button.offsetLeft < rail.scrollLeft) rail.scrollLeft = button.offsetLeft;
  else if (button.offsetLeft + button.offsetWidth > rail.scrollLeft + rail.clientWidth) rail.scrollLeft = button.offsetLeft + button.offsetWidth - rail.clientWidth;
  if (button.offsetTop < rail.scrollTop) rail.scrollTop = button.offsetTop;
  else if (button.offsetTop + button.offsetHeight > rail.scrollTop + rail.clientHeight) rail.scrollTop = button.offsetTop + button.offsetHeight - rail.clientHeight;
}

export function ProductGallery({ product }: { product: PublicProductDetail }) {
  const [selected, setSelected] = useState(0);
  const [interacted, setInteracted] = useState(false);
  const [failedUrls, setFailedUrls] = useState<string[]>([]);
  const thumbnailRail = useRef<HTMLDivElement>(null);
  const images = product.images;
  const selectedIndex = Math.min(selected, Math.max(images.length - 1, 0));
  const image = images[selectedIndex];
  const imageLabel = (item: ProductImage, index: number) => item.alt_text.trim() || `${product.name}, image ${index + 1}`;

  function selectImage(index: number) {
    if (index === selectedIndex) return;
    setInteracted(true);
    setSelected(index);
  }

  function moveImage(direction: number) {
    selectImage(galleryImageIndex(selectedIndex, direction, images.length));
  }

  function onGalleryKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (images.length < 2 || event.altKey || event.ctrlKey || event.metaKey) return;
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const thumbnail = event.target instanceof HTMLElement ? event.target.closest<HTMLButtonElement>("[data-image-index]") : null;
    const current = thumbnail ? Number(thumbnail.dataset.imageIndex) : selectedIndex;
    const next = event.key === "Home" ? 0 : event.key === "End" ? images.length - 1 : galleryImageIndex(current, event.key === "ArrowRight" ? 1 : -1, images.length);
    selectImage(next);
    if (thumbnail) revealThumbnail(thumbnailRail.current, next, true);
  }

  useEffect(() => {
    revealThumbnail(thumbnailRail.current, selectedIndex);
  }, [selectedIndex]);

  return (
    <section aria-label="Product images" aria-roledescription={images.length > 1 ? "carousel" : undefined} className="product-gallery" onKeyDown={onGalleryKeyDown}>
      <figure className="product-gallery-figure">
        <div aria-describedby={images.length > 1 ? "product-gallery-help" : undefined} aria-label={images.length > 1 ? "Selected product image" : undefined} className="product-gallery-stage" role={images.length > 1 ? "group" : undefined} tabIndex={images.length > 1 ? 0 : undefined}>
          {image && !failedUrls.includes(image.image_url) ? (
            <img
              alt={imageLabel(image, selectedIndex)}
              className="product-gallery-image"
              data-interacted={interacted}
              height={image.height}
              key={image.image_url}
              onError={() => setFailedUrls((current) => [...current, image.image_url])}
              src={image.image_url}
              width={image.width}
            />
          ) : <span className="product-image-fallback">Image unavailable</span>}
        </div>
        {images.length > 1 ? (
          <figcaption className="product-gallery-controls">
            <button aria-label="Previous product image" className="product-icon-button" onClick={() => moveImage(-1)} type="button"><StoreIcon inheritColor name="previous" /></button>
            <span aria-live="polite" aria-atomic="true" className="product-gallery-count">Image {selectedIndex + 1} of {images.length}</span>
            <button aria-label="Next product image" className="product-icon-button" onClick={() => moveImage(1)} type="button"><StoreIcon inheritColor name="next" /></button>
          </figcaption>
        ) : null}
        {images.length > 1 ? <p className="sr-only" id="product-gallery-help">Use Left and Right arrow keys to change images, or Home and End for the first and last image.</p> : null}
      </figure>
      {images.length > 1 ? (
        <div aria-label="Choose a product image" className="product-gallery-thumbnails" ref={thumbnailRail} role="group">
          {images.map((item, index) => (
            <button aria-label={`View image ${index + 1}: ${imageLabel(item, index)}`} aria-pressed={selectedIndex === index} className="product-gallery-thumbnail" data-image-index={index} key={item.id} onClick={() => selectImage(index)} type="button">
              {failedUrls.includes(item.image_url) ? <span className="text-xs">Image unavailable</span> : (
                <img alt="" height={item.height} loading="lazy" onError={() => setFailedUrls((current) => [...current, item.image_url])} src={item.image_url} width={item.width} />
              )}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
