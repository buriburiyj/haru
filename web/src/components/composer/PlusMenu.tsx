import { useState } from "react";
import { IconButton, Menu, MenuItem, SubMenu } from "../ui";
import { useDismiss } from "./ui";

const SUB: Record<string, string[]> = {
  project: ["프로젝트 없음", "새 프로젝트 만들기"],
  skills: ["등록된 Skills 없음", "Skills 관리"],
  connectors: ["연결된 커넥터 없음", "커넥터 관리"],
};

export default function PlusMenu({
  webSearch,
  onToggleWebSearch,
}: {
  webSearch: boolean;
  onToggleWebSearch: () => void;
}) {
  const [open, setOpen] = useState(false);
  const close = () => {
    setOpen(false);
  };
  const ref = useDismiss(open, close);

  const items = (key: string) =>
    SUB[key].map((t) => (
      <MenuItem key={t} onClick={close}>
        {t}
      </MenuItem>
    ));

  return (
    <div ref={ref} className="relative">
      <IconButton label="추가" aria-expanded={open} onClick={() => (open ? close() : setOpen(true))}>
        <span className="text-lg">+</span>
      </IconButton>
      {open && (
        <Menu className="absolute bottom-full left-0 z-20 mb-2">
          <MenuItem shortcut="⌘U" onClick={close}>
            파일 업로드
          </MenuItem>
          <SubMenu label="프로젝트에 추가">{items("project")}</SubMenu>
          <SubMenu label="Skills">{items("skills")}</SubMenu>
          <SubMenu label="커넥터">{items("connectors")}</SubMenu>
          <MenuItem onClick={close}>플러그인 추가</MenuItem>
          <MenuItem toggle={webSearch} onClick={onToggleWebSearch}>
            웹 검색
          </MenuItem>
        </Menu>
      )}
    </div>
  );
}
