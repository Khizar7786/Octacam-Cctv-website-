import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "~/lib/utils";

export interface ContainerProps extends HTMLAttributes<HTMLDivElement> {
  size?: "page" | "reading";
}

export const Container = forwardRef<HTMLDivElement, ContainerProps>(
  ({ className, size = "page", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "min-w-0 w-full px-[var(--page-gutter)]",
        size === "reading" && "mx-auto max-w-[var(--reading-max)]",
        className,
      )}
      {...props}
    />
  ),
);

Container.displayName = "Container";
