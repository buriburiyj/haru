import { useState } from "react";
import { TempChatToggle } from "../temp/TempChat";

export default function TopBar({ title, onMenu }: { title: string; onMenu: () => void }) {
  const [open, setOpen] = useState(false);
  const item = "block w-full px-3 py-2 text-left text-sm hover:bg-surface-2";
  return (
    <div className="flex items-center gap-2 border-b border-line bg-bg px-3 py-2">
      <button type="button" onClick={onMenu} aria-label="메뉴" className="rounded-md px-2 py-1 text-fg hover:bg-surface-2 md:hidden">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <div className="relative min-w-0 flex-1">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex max-w-full items-center gap-1 rounded-md px-2 py-1 text-fg hover:bg-surface-2"
        >
          <span className="truncate font-medium">{title}</span>
          <span className="text-muted">▾</span>
        </button>
        {open && (
          <div className="absolute left-0 top-full z-10 mt-1 w-44 overflow-hidden rounded-lg border border-line bg-surface py-1 text-fg">
            <button type="button" className={item} onClick={() => setOpen(false)}>이름 변경</button>
            <button type="button" className={item} onClick={() => setOpen(false)}>프로젝트로 이동</button>
            <button type="button" className={`${item} text-danger`} onClick={() => setOpen(false)}>삭제</button>
          </div>
        )}
      </div>
      <TempChatToggle />
      <button type="button" className="rounded-md px-3 py-1 text-sm text-fg hover:bg-surface-2">
        내보내기
      </button>
    </div>
  );
}
