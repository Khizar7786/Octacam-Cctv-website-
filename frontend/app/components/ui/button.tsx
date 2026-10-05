import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "~/lib/utils";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost";

const variants: Record<ButtonVariant, string> = {
  primary:
    "border-primary bg-primary text-primary-foreground shadow-sm hover:border-primary-hover hover:bg-primary-hover",
  secondary:
    "border-border-strong bg-secondary text-secondary-foreground hover:bg-muted",
  outline:
    "border-border-strong bg-card text-foreground hover:border-primary hover:bg-accent hover:text-accent-foreground",
  ghost:
    "border-transparent bg-transparent text-foreground hover:bg-accent hover:text-accent-foreground",
};

export function buttonStyles({
  className,
  variant = "primary",
}: {
  className?: string;
  variant?: ButtonVariant;
} = {}) {
  return cn(
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-md border px-4 py-2 text-sm font-semibold no-underline transition-[background-color,border-color,color,box-shadow] duration-[var(--motion-duration-fast)] ease-[var(--motion-ease-standard)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
    variants[variant],
    className,
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, type = "button", variant = "primary", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={buttonStyles({ className, variant })}
      {...props}
    />
  ),
);

Button.displayName = "Button";
