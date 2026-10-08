import type { ImgHTMLAttributes } from "react";
import { cn } from "~/lib/utils";

export type OctacamLogoProps = Omit<
  ImgHTMLAttributes<HTMLImageElement>,
  "height" | "src" | "width"
>;

export function OctacamLogo({ alt = "OctaCam", className, ...props }: OctacamLogoProps) {
  return (
    <img
      alt={alt}
      className={cn("aspect-square h-auto w-full object-contain", className)}
      height={1254}
      src="/brand/octacam-logo.png"
      width={1254}
      {...props}
    />
  );
}

/** Owner-approved horizontal composition; both pieces use the unchanged master. */
export function OctacamWordmark() {
  return (
    <span aria-hidden="true" className="inline-flex items-center gap-2">
      <svg className="h-10 w-16 overflow-hidden" viewBox="215 285 815 515" focusable="false">
        <image height="1254" href="/brand/octacam-logo.png" width="1254" />
      </svg>
      <svg className="hidden h-7 w-36 overflow-hidden sm:block" viewBox="80 835 1100 205" focusable="false">
        <image height="1254" href="/brand/octacam-logo.png" width="1254" />
      </svg>
    </span>
  );
}
