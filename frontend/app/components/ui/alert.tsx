import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "~/lib/utils";

export type AlertVariant = "info" | "success" | "warning" | "error";

const variants: Record<AlertVariant, string> = {
  info: "border-info bg-info-surface text-info",
  success: "border-success bg-success-surface text-success",
  warning: "border-warning bg-warning-surface text-warning",
  error: "border-error bg-error-surface text-error",
};

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: AlertVariant;
}

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = "info", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "grid gap-1 rounded-md border border-l-4 px-4 py-3 text-sm",
        variants[variant],
        className,
      )}
      {...props}
    />
  ),
);

Alert.displayName = "Alert";

export const AlertTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("font-semibold leading-snug", className)} {...props} />
  ),
);

AlertTitle.displayName = "AlertTitle";

export const AlertDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("leading-relaxed text-foreground", className)} {...props} />
  ),
);

AlertDescription.displayName = "AlertDescription";
