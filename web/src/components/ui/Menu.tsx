import type { ButtonHTMLAttributes, HTMLAttributes } from "react";
import { cx } from "./cx";

/** Popup list. The parent positions it (e.g. absolute right-0 top-full) and owns open/close. */
export function Menu({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="menu"
      className={cx("flex min-w-44 flex-col rounded-card border border-line bg-surface p-1 shadow-pop", className)}
      {...rest}
    />
  );
}

export function MenuItem({
  danger,
  className,
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { danger?: boolean }) {
  return (
    <button
      type={type}
      role="menuitem"
      className={cx(
        "min-h-11 rounded-control px-3 text-left text-sm hover:bg-surface-2",
        danger ? "text-danger" : "text-fg",
        className,
      )}
      {...rest}
    />
  );
}

export function MenuDivider() {
  return <div role="separator" className="my-1 border-t border-line" />;
}
