import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "~/lib/utils";

export interface StackProps extends HTMLAttributes<HTMLDivElement> {
  gap?: "compact" | "default" | "section";
}

const gaps = {
  compact: "gap-3",
  default: "gap-6",
  section: "gap-12 sm:gap-16",
} as const;

export const Stack = forwardRef<HTMLDivElement, StackProps>(
  ({ className, gap = "default", ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col", gaps[gap], className)} {...props} />
  ),
);

Stack.displayName = "Stack";
