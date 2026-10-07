import { useState } from "react";
import { Link } from "react-router";
import { promotions } from "~/config/promotions";

function PromoArtwork({
  desktopImage,
  mobileImage,
}: {
  desktopImage: string;
  mobileImage: string;
}) {
  const [failed, setFailed] = useState(false);

  return (
    <div className="relative flex min-h-48 items-center justify-center overflow-hidden bg-accent sm:min-h-64 lg:min-h-full">
      <div className="relative rounded-lg border border-primary/20 bg-card/90 px-6 py-4 text-xl font-bold text-foreground">
        Octa<span className="text-primary">Cam</span>
      </div>
      {!failed ? (
        <picture className="absolute inset-0">
          <source media="(max-width: 639px)" srcSet={mobileImage} />
          <img
            alt=""
            className="h-full w-full object-cover"
            height={600}
            onError={() => setFailed(true)}
            src={desktopImage}
            width={960}
          />
        </picture>
      ) : null}
    </div>
  );
}

export function PromoCarousel() {
  const [activeIndex, setActiveIndex] = useState(0);
  const promotion = promotions[activeIndex];

  function move(amount: number) {
    setActiveIndex((current) => (current + amount + promotions.length) % promotions.length);
  }

  return (
    <section aria-label="Promotions" className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
      <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,0.92fr)]">
        <div className="flex flex-col justify-center p-5 sm:p-8 lg:min-h-[22rem] lg:p-10">
          <p className="mb-3 text-sm font-semibold text-primary">OctaCam · CCTV equipment</p>
          <h1 className="max-w-xl text-[length:var(--font-size-display)] font-bold leading-[var(--line-height-tight)] tracking-[-0.045em]">
            {promotion.title}
          </h1>
          <p className="mt-3 max-w-lg text-base text-muted-foreground sm:text-lg">{promotion.description}</p>
          <Link
            className="mt-5 inline-flex min-h-11 w-fit items-center rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground no-underline hover:bg-primary-hover hover:text-primary-foreground"
            to={promotion.to}
          >
            {promotion.actionLabel}
            <span aria-hidden="true" className="ml-3">→</span>
          </Link>
        </div>
        <PromoArtwork
          key={promotion.id}
          desktopImage={promotion.desktopImage}
          mobileImage={promotion.mobileImage}
        />
      </div>

      {promotions.length > 1 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-2 sm:px-8 lg:px-10">
          <p aria-live="polite" className="text-sm text-muted-foreground">
            Promotion {activeIndex + 1} of {promotions.length}: <span className="font-semibold text-foreground">{promotion.title}</span>
          </p>
          <div className="flex items-center gap-2">
            <button
              aria-label="Previous promotion"
              className="min-h-11 rounded-md border border-border-strong px-3 text-sm font-semibold text-foreground hover:bg-accent"
              onClick={() => move(-1)}
              type="button"
            >
              Previous
            </button>
            <button
              aria-label="Next promotion"
              className="min-h-11 rounded-md border border-border-strong px-3 text-sm font-semibold text-foreground hover:bg-accent"
              onClick={() => move(1)}
              type="button"
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
