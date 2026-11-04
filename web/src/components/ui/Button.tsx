import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-fg hover:bg-accent-hover",
  secondary: "border border-line bg-surface text-fg hover:bg-surface-2",
  ghost: "text-fg hover:bg-surface-2",
  danger: "bg-danger text-accent-fg hover:opacity-90",
};

/** The one button. Compact with a mouse, 44px on touch screens; rounded-control; accent only for the main action. */
const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }>(
  function Button({ variant = "secondary", className, type = "button", ...rest }, ref) {
    return (
      <button
        ref={ref}
        type={type}
        className={cx(
          "inline-flex min-h-9 pointer-coarse:min-h-11 items-center justify-center gap-2 rounded-control px-4 text-sm font-medium transition-colors disabled:opacity-50",
          VARIANT[variant],
          className,
        )}
        {...rest}
      />
    );
  },
);

export default Button;
