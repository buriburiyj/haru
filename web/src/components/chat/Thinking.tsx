import { useState } from "react";

export default function Thinking({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="my-1 max-w-full">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-muted hover:bg-surface-2 hover:text-fg"
      >
        <span aria-hidden>{open ? "▾" : "▸"}</span>
        생각 과정
      </button>
      {open && <div className="mt-1 whitespace-pre-wrap break-words border-l-2 border-line pl-3 text-sm text-muted">{text.trim()}</div>}
    </div>
  );
}
