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
        "mx-auto w-full px-4 sm:px-6 lg:px-8",
        size === "reading" ? "max-w-[var(--reading-max)]" : "max-w-[var(--page-max)]",
        className,
      )}
      {...props}
    />
  ),
);

Container.displayName = "Container";
