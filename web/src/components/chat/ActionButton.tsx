import type { ReactNode } from "react";
import { Button } from "../ui";

export default function ActionButton({ label, onClick, pressed, children }: { label: string; onClick?: () => void; pressed?: boolean; children: ReactNode }) {
  return (
    <Button variant="ghost" title={label} aria-label={label} aria-pressed={pressed} onClick={onClick} className={pressed ? "px-2 text-xs text-fg" : "px-2 text-xs text-muted hover:text-fg"}>
      {children}
    </Button>
  );
}

export function copyText(text: string) {
  try {
    void navigator.clipboard.writeText(text);
    window.dispatchEvent(new CustomEvent("haru:copied"));
  } catch {
    /* clipboard unavailable */
  }
}
