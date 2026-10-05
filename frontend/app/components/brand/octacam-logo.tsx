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
