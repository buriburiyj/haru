import type { HTMLAttributes } from "react";
import { cx } from "./cx";

/** My message: right-aligned bubble, UI font. */
export function UserBubble({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className="flex justify-end">
      <div
        className={cx("max-w-[85%] whitespace-pre-wrap break-words rounded-bubble bg-bubble px-4 py-2.5 text-fg", className)}
        {...rest}
      />
    </div>
  );
}

/** Haru's answer: no bubble, left, book-like reading font (see data-font in tokens.css). */
export function Reply({ className, style, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx("w-full break-words font-reading text-fg", className)}
      style={{ fontSize: "var(--haru-reading-size)", lineHeight: "var(--haru-reading-leading)", ...style }}
      {...rest}
    />
  );
}
