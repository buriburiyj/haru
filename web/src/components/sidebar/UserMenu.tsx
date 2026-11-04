import { useState } from "react";
import { Button, Menu, MenuDivider, MenuItem } from "../ui";

const items = ["설정", "언어", "도움말", "기기 연결", "단축키"];

export default function UserMenu({ userName, onLogout }: { userName: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative border-t border-line pt-2">
      {open && (
        <Menu className="absolute bottom-full left-0 right-0 mb-1">
          {items.map((t) => (
            <MenuItem key={t} onClick={() => {
                setOpen(false);
                if (t === "설정") window.dispatchEvent(new Event("haru:open-settings"));
              }}>
              {t}
            </MenuItem>
          ))}
          <MenuDivider />
          <MenuItem
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
          >
            로그아웃
          </MenuItem>
        </Menu>
      )}
      <Button
        variant="ghost"
        onClick={() => setOpen((v) => !v)}
        className="w-full justify-start gap-2 px-2 font-normal"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-pill bg-accent text-xs text-accent-fg">
          {userName.slice(0, 1).toUpperCase()}
        </span>
        <span className="flex-1 truncate text-left text-sm text-fg">{userName}</span>
        <span className="text-muted">▾</span>
      </Button>
    </div>
  );
}
