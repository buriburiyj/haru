import { useEffect } from "react";
import type { ReactNode } from "react";
import { IconButton } from "../ui";

/**
 * Full-screen page used for 채팅 목록 / 프로젝트 / 아티팩트. Sits above the app (z-40), Esc closes.
 * On desktop the sidebar stays visible next to it (left-64); on phone it covers everything.
 */
export default function PageShell({
  title,
  onClose,
  actions,
  children,
}: {
  title: string;
  onClose: () => void;
  actions?: ReactNode;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-bg text-fg md:left-64">
      <header className="flex items-center gap-2 border-b border-line px-4 py-3">
        <IconButton label="닫기" onClick={onClose}>
          ←
        </IconButton>
        <h1 className="mr-auto text-lg font-semibold">{title}</h1>
        {actions}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-5">{children}</div>
      </div>
    </div>
  );
}
