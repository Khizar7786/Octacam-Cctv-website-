import { useEffect, useRef, useState } from "react";
import type { CSSProperties, PointerEvent } from "react";
import { Link } from "react-router";
import { promotions, promotionTiming } from "~/config/promotions";
import { usePromoPlayback } from "./use-promo-playback";
import "~/styles/promotions.css";

function PromoArtwork({ desktopImage, mobileImage, eager }: {
  desktopImage: string;
  mobileImage: string;
  eager: boolean;
}) {
  const [failed, setFailed] = useState(false);

  return (
    <div className="promo-artwork" data-image-failed={failed}>
      {!failed ? (
        <picture>
          <source media="(max-width: 639px)" srcSet={mobileImage} />
          <img
            alt=""
            fetchPriority={eager ? "high" : "auto"}
            height={480}
            loading={eager ? "eager" : "lazy"}
            onError={() => setFailed(true)}
            src={desktopImage}
            width={1920}
          />
        </picture>
      ) : null}
    </div>
  );
}

/** Reserve the full heading's height; screen readers hear the complete text once. */
function TypewriterTitle({ title, typeOnLoad, active, onComplete }: {
  title: string;
  typeOnLoad: boolean;
  active: boolean;
  onComplete: (complete: boolean) => void;
}) {
  const [length, setLength] = useState<number | null>(null);
  const characters = Array.from(title);

  useEffect(() => {
    if (!typeOnLoad) {
      setLength(null);
      return;
    }
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (preference.matches) {
      onComplete(true);
      return;
    }

    let timer = 0;
    let count = 0;
    const total = Array.from(title).length;
    setLength(0);
    const type = () => {
      count += 1;
      setLength(count);
      if (count < total) timer = window.setTimeout(type, promotionTiming.characterMs);
      else {
        setLength(null);
        onComplete(true);
      }
    };
    timer = window.setTimeout(type, promotionTiming.typingDelayMs);
    const finish = () => {
      if (!preference.matches) return;
      window.clearTimeout(timer);
      setLength(null);
      onComplete(true);
    };
    preference.addEventListener("change", finish);
    return () => {
      window.clearTimeout(timer);
      preference.removeEventListener("change", finish);
    };
    // This runs once on the initial page load, never when slides rotate or hover ends.
  }, [title, typeOnLoad, onComplete]);

  const Heading = active ? "h1" : "h2";
  const typing = active && length !== null;
  return (
    <Heading className="promo-title">
      <span className="sr-only">{title}</span>
      <span aria-hidden="true" className="promo-title-measure">{title}</span>
      <span aria-hidden="true" className="promo-title-visual">
        {typing ? characters.slice(0, length).join("") : title}
        {typing ? <span className="promo-cursor" /> : null}
      </span>
    </Heading>
  );
}

export function PromoCarousel() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [typingComplete, setTypingComplete] = useState(false);
  const playback = usePromoPlayback(promotions.length, activeIndex, () => {
    setActiveIndex((current) => (current + 1) % promotions.length);
  });
  const swipeStart = useRef<{ x: number; y: number } | null>(null);
  const suppressClick = useRef(false);
  const clickTimer = useRef(0);

  useEffect(() => () => window.clearTimeout(clickTimer.current), []);

  function select(index: number) {
    setTypingComplete(true);
    setActiveIndex((index + promotions.length) % promotions.length);
  }

  function finishSwipe(event: PointerEvent<HTMLElement>) {
    const start = swipeStart.current;
    swipeStart.current = null;
    if (!start) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
    select(activeIndex + (dx < 0 ? 1 : -1));
    // A horizontal swipe over a link must not also navigate to that campaign.
    suppressClick.current = true;
    window.clearTimeout(clickTimer.current);
    clickTimer.current = window.setTimeout(() => { suppressClick.current = false; }, 300);
  }

  return (
    <section
      aria-label="Featured promotions"
      aria-roledescription="carousel"
      className="promo-carousel"
      data-running={playback.running}
      onClickCapture={(event) => {
        if (suppressClick.current) {
          event.preventDefault();
          event.stopPropagation();
          suppressClick.current = false;
        }
      }}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) playback.setFocused(false);
      }}
      onFocusCapture={() => playback.setFocused(true)}
      onMouseEnter={() => playback.setHovered(true)}
      onMouseLeave={() => playback.setHovered(false)}
      onPointerCancel={() => { swipeStart.current = null; }}
      onPointerDown={(event) => {
        if (event.pointerType === "touch" && !(event.target as HTMLElement).closest("button")) {
          swipeStart.current = { x: event.clientX, y: event.clientY };
        }
      }}
      onPointerUp={finishSwipe}
      ref={playback.sectionRef}
      style={{ "--promo-interval": `${promotionTiming.slideMs}ms` } as CSSProperties}
    >
      <div className="promo-window">
        <div
          aria-live={playback.running ? "off" : "polite"}
          className="promo-track"
          id="promotion-slides"
          style={{ transform: `translateX(-${activeIndex * 100}%)` }}
        >
          {promotions.map((promotion, index) => (
            <div
              aria-hidden={index !== activeIndex}
              aria-label={`${index + 1} of ${promotions.length}`}
              aria-roledescription="slide"
              className="promo-slide"
              inert={index !== activeIndex}
              key={promotion.id}
              role="group"
            >
              <PromoArtwork desktopImage={promotion.desktopImage} mobileImage={promotion.mobileImage} eager={index === 0} />
              <div className="promo-copy">
                <p className="promo-label">{promotion.label}</p>
                <TypewriterTitle
                  active={index === activeIndex}
                  onComplete={setTypingComplete}
                  typeOnLoad={index === 0 && !typingComplete}
                  title={promotion.title}
                />
                <p className="promo-description">{promotion.description}</p>
                <Link className="promo-action" to={promotion.to}>{promotion.actionLabel}</Link>
              </div>
            </div>
          ))}
        </div>
      </div>

      {promotions.length > 1 ? (
        <div aria-label="Choose a promotion" className="promo-pagination" role="group">
          {promotions.map((promotion, index) => (
            <button
              aria-controls="promotion-slides"
              aria-label={`Show promotion ${index + 1}: ${promotion.title}`}
              aria-pressed={index === activeIndex}
              className="promo-picker"
              key={promotion.id}
              onClick={() => select(index)}
              type="button"
            >
              <span className="promo-picker-track" key={`${index}-${activeIndex}`} />
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
