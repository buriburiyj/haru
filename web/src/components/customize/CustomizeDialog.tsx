import { useEffect, useState } from "react";
import { IconButton } from "../ui";
import CustomizePanel from "./CustomizePanel";
import type { Kind } from "./sample";

/** Sidebar "사용자 지정" popup. Uses the same CustomizePanel as Settings. */
export default function CustomizeDialog({ onClose, initial = "skills" }: { onClose: () => void; initial?: Kind }) {
  const [kind, setKind] = useState<Kind>(initial);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-center bg-fg/40 md:items-center md:p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-label="사용자 지정"
        className="relative flex h-full w-full flex-col overflow-y-auto bg-bg p-5 text-fg md:h-160 md:max-h-full md:max-w-3xl md:rounded-card md:border md:border-line"
      >
        <IconButton label="닫기" onClick={onClose} className="absolute right-4 top-4">
          ✕
        </IconButton>
        <CustomizePanel kind={kind} onKindChange={setKind} />
      </div>
    </div>
  );
}
