import type { ButtonHTMLAttributes } from "react";
import { cx } from "./cx";

/** Icon-only button, 44x44. `label` is required (screen readers and tooltip). */
export default function IconButton({
  label,
  active,
  className,
  type = "button",
  children,
  ...rest
}: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label"> & { label: string; active?: boolean }) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      aria-pressed={active}
      className={cx(
        "inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-control transition-colors hover:bg-surface-2",
        active ? "text-accent" : "text-muted hover:text-fg",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
