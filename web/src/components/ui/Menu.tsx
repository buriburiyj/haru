import { useState } from "react";
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

/** Popup list. The parent positions it (e.g. absolute left-0 bottom-full) and owns open/close. */
export function Menu({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="menu"
      className={cx("flex min-w-52 flex-col rounded-card border border-line bg-surface p-1 shadow-pop", className)}
      {...rest}
    />
  );
}

type ItemExtras = {
  danger?: boolean;
  /** small icon before the label */
  icon?: ReactNode;
  /** selected choice: shows ✓ on the right */
  check?: boolean;
  /** on/off switch on the right (shows the switch, sets role=menuitemcheckbox) */
  toggle?: boolean;
  /** shortcut hint on the right, e.g. "1" or "⌘K" */
  shortcut?: string;
  /** one-line explanation under the label */
  hint?: string;
  /** opens a sub menu: shows › on the right */
  submenu?: boolean;
};

export function MenuItem({
  danger,
  icon,
  check,
  toggle,
  shortcut,
  hint,
  submenu,
  className,
  type = "button",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & ItemExtras) {
  const isToggle = toggle !== undefined;
  return (
    <button
      type={type}
      role={isToggle ? "menuitemcheckbox" : "menuitem"}
      aria-checked={isToggle ? toggle : check}
      className={cx(
        "flex min-h-9 pointer-coarse:min-h-11 w-full items-center gap-2 rounded-control px-3 text-left text-sm hover:bg-surface-2",
        danger ? "text-danger" : "text-fg",
        className,
      )}
      {...rest}
    >
      {icon && <span className="shrink-0 text-muted">{icon}</span>}
      <span className="min-w-0 flex-1">
        <span className="block truncate">{children}</span>
        {hint && <span className="block truncate text-xs text-muted">{hint}</span>}
      </span>
      {isToggle && (
        <span
          aria-hidden="true"
          className={cx("relative h-6 w-10 shrink-0 rounded-pill border border-line", toggle ? "bg-accent" : "bg-surface-2")}
        >
          <span className={cx("absolute top-0.5 h-4 w-4 rounded-pill bg-bg", toggle ? "left-5" : "left-0.5")} />
        </span>
      )}
      {check && <span className="shrink-0 text-accent" aria-hidden="true">✓</span>}
      {shortcut && <kbd className="shrink-0 rounded-control border border-line px-1.5 text-xs text-muted" style={{ fontFamily: "inherit" }}>{shortcut}</kbd>}
      {submenu && <span className="shrink-0 text-muted" aria-hidden="true">›</span>}
    </button>
  );
}

export function MenuDivider() {
  return <div role="separator" className="my-1 border-t border-line" />;
}

/**
 * Item that opens a sub menu. Desktop: panel opens to the side (`side`: right by default, left for menus near the right edge).
 * Phone: the panel opens indented right under the item (no side space).
 */
export function SubMenu({ label, children, side = "right", ...extras }: { label: ReactNode; children: ReactNode; side?: "left" | "right" } & ItemExtras) {
  const [open, setOpen] = useState(false);
  return (
    <div className="group relative" onMouseLeave={() => setOpen(false)}>
      <MenuItem {...extras} submenu aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((v) => !v)} onMouseEnter={() => setOpen(true)}>
        {label}
      </MenuItem>
      {open && (
        <Menu className={cx("mt-1 ml-3 md:absolute md:top-0 md:mt-0 md:ml-0", side === "left" ? "md:right-full md:mr-1" : "md:left-full md:ml-1")}>{children}</Menu>
      )}
    </div>
  );
}
