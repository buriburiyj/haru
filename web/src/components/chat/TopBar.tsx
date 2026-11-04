import { useState } from "react";
import { TempChatToggle } from "../temp/TempChat";
import ConfirmDialog from "../confirm/ConfirmDialog";
import { Button, Dialog, IconButton, Input, Menu, MenuItem } from "../ui";

export default function TopBar({
  title,
  onMenu,
  onDelete,
  onRename,
}: {
  title: string;
  onMenu: () => void;
  onDelete?: () => void;
  onRename?: (title: string) => void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState("");
  const saveName = () => {
    const t = draft.trim();
    if (!t) return;
    setRenaming(false);
    onRename?.(t);
  };
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  return (
    <div className="flex items-center gap-2 border-b border-line bg-bg px-3 py-2">
      <IconButton label="메뉴" onClick={onMenu} className="text-fg md:hidden">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </IconButton>
      <div className="relative min-w-0 flex-1">
        <Button variant="ghost" onClick={() => setOpen(!open)} className="max-w-full gap-1 px-2">
          <span className="truncate font-medium">{title}</span>
          <span className="text-muted">▾</span>
        </Button>
        {open && (
          <Menu className="absolute left-0 top-full z-10 mt-1 w-44">
            <MenuItem onClick={() => { setOpen(false); if (onRename) { setDraft(title); setRenaming(true); } }}>이름 변경</MenuItem>
            <MenuItem onClick={() => setOpen(false)}>프로젝트로 이동</MenuItem>
            <MenuItem danger onClick={() => { setOpen(false); setConfirming(true); }}>삭제</MenuItem>
          </Menu>
        )}
      </div>
      <TempChatToggle />
      <Button variant="ghost">내보내기</Button>
      {renaming && (
        <Dialog
          title="이름 변경"
          onClose={() => setRenaming(false)}
          footer={
            <>
              <Button onClick={() => setRenaming(false)}>취소</Button>
              <Button variant="primary" disabled={!draft.trim()} onClick={saveName}>
                저장
              </Button>
            </>
          }
        >
          <Input
            autoFocus
            aria-label="채팅 이름"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && saveName()}
          />
        </Dialog>
      )}
      {confirming && (
        <ConfirmDialog
          title="이 채팅을 삭제할까요?"
          message="삭제하면 되돌릴 수 없습니다."
          onCancel={() => setConfirming(false)}
          onConfirm={() => {
            setConfirming(false);
            onDelete?.();
          }}
        />
      )}
    </div>
  );
}
