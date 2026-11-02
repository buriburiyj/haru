import type { ReactNode } from "react";

export default function ActionButton({ label, onClick, children }: { label: string; onClick?: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className="rounded-md px-1.5 py-1 text-xs text-muted hover:bg-surface-2 hover:text-fg"
    >
      {children}
    </button>
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
