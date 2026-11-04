import { useState } from "react";
import { Button } from "../ui";

export default function Thinking({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="my-1 max-w-full">
      <Button
        variant="ghost"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="gap-1 px-2 text-xs text-muted hover:text-fg"
      >
        <span aria-hidden>{open ? "▾" : "▸"}</span>
        생각 과정
      </Button>
      {open && <div className="mt-1 whitespace-pre-wrap break-words border-l-2 border-line pl-3 text-sm text-muted">{text.trim()}</div>}
    </div>
  );
}
