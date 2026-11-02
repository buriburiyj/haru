import { useState } from "react";

const items = ["설정", "언어", "도움말", "기기 연결", "단축키"];

export default function UserMenu({ userName, onLogout }: { userName: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const itemCls = "w-full rounded-lg px-2 py-1.5 text-left text-sm text-fg hover:bg-surface-2";
  return (
    <div className="relative border-t border-line pt-2">
      {open && (
        <div className="absolute bottom-full left-0 right-0 mb-1 flex flex-col rounded-xl border border-line bg-surface p-1 shadow-lg">
          {items.map((t) => (
            <button key={t} type="button" className={itemCls} onClick={() => {
                setOpen(false);
                if (t === "설정") window.dispatchEvent(new Event("haru:open-settings"));
              }}>
              {t}
            </button>
          ))}
          <div className="my-1 border-t border-line" />
          <button
            type="button"
            className={itemCls}
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
          >
            로그아웃
          </button>
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-2"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-xs text-accent-fg">
          {userName.slice(0, 1).toUpperCase()}
        </span>
        <span className="flex-1 truncate text-left text-sm text-fg">{userName}</span>
        <span className="text-muted">▾</span>
      </button>
    </div>
  );
}
