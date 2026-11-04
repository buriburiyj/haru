import type { HTMLAttributes } from "react";
import { cx } from "./cx";

/** Surface block: settings groups, template cards, list items. */
export default function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx("rounded-card border border-line bg-surface p-4", className)} {...rest} />;
}
