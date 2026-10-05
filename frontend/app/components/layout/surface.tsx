import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "~/lib/utils";

export interface SurfaceProps extends HTMLAttributes<HTMLDivElement> {
  tone?: "default" | "subtle";
}

export const Surface = forwardRef<HTMLDivElement, SurfaceProps>(
  ({ className, tone = "default", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border border-border p-5 shadow-sm sm:p-6",
        tone === "subtle" ? "bg-muted" : "bg-card",
        className,
      )}
      {...props}
    />
  ),
);

Surface.displayName = "Surface";
