import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cx } from "./cx";

const BASE =
  "w-full rounded-control border border-line bg-surface px-4 text-fg outline-none transition-colors placeholder:text-muted focus:border-accent";

/** Single-line input, 44px high. Focus shows the accent border. */
export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(BASE, "min-h-10 pointer-coarse:min-h-11", className)} {...rest} />;
}

/** Multi-line input. */
export function Textarea({ className, rows = 3, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={rows} className={cx(BASE, "py-2.5", className)} {...rest} />;
}
