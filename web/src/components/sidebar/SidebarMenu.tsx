import { useState } from "react";
import type { ReactNode } from "react";
import type { ChatRow } from "../chat/dataTypes";
import { Button, IconButton } from "../ui";
import {
  ArtifactIcon,
  ChevronDownIcon,
  CustomizeIcon,
  FolderIcon,
  PlusIcon,
  SearchIcon,
} from "./icons";

const itemCls = "w-full justify-start gap-2 px-2 text-left font-normal";

function MenuItem({ icon, label, onClick }: { icon: ReactNode; label: string; onClick?: () => void }) {
  return (
    <Button variant="ghost" onClick={onClick} className={itemCls}>
      <span className="text-muted">{icon}</span>
      {label}
    </Button>
  );
}

export default function SidebarMenu({
  chats,
  activeId,
  onNew,
  onOpenChat,
}: {
  chats: ChatRow[];
  activeId?: string;
  onNew: () => void;
  onOpenChat: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
      <nav className="flex flex-col gap-0.5">
        <MenuItem icon={<PlusIcon />} label="새로 만들기" onClick={onNew} />
        <MenuItem icon={<SearchIcon />} label="검색" onClick={() => window.dispatchEvent(new Event("haru:open-search"))} />
        <div className="group/proj relative">
          <MenuItem icon={<FolderIcon />} label="프로젝트" onClick={() => window.dispatchEvent(new Event("haru:open-projects"))} />
          <IconButton
            label="새 프로젝트"
            onClick={() => window.dispatchEvent(new Event("haru:new-project"))}
            className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 focus:opacity-100 group-hover/proj:opacity-100 pointer-coarse:opacity-100"
          >
            +
          </IconButton>
        </div>
        <MenuItem icon={<ArtifactIcon />} label="아티팩트" onClick={() => window.dispatchEvent(new Event("haru:open-artifacts"))} />
        <MenuItem icon={<CustomizeIcon />} label="사용자 지정" onClick={() => window.dispatchEvent(new Event("haru:open-customize"))} />
      </nav>
      <section className="flex flex-col gap-0.5">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-1 px-2 py-1 pointer-coarse:min-h-11 text-xs text-muted hover:text-fg"
        >
          채팅 및 작업
          <span className={expanded ? "" : "-rotate-90"}>
            <ChevronDownIcon />
          </span>
        </button>
        {expanded && (
          <>
            {chats.length === 0 && <p className="px-2 py-1 text-xs text-muted">아직 대화가 없습니다</p>}
            {chats.slice(0, 7).map((c) => (
              <Button
                key={c.id}
                variant="ghost"
                onClick={() => onOpenChat(c.id)}
                aria-current={c.id === activeId ? "true" : undefined}
                className={itemCls + " justify-between" + (c.id === activeId ? " bg-surface-2" : "")}
              >
                <span className="truncate">{c.title}</span>
                <span className="shrink-0 text-xs text-muted">{c.when}</span>
              </Button>
            ))}
            <button
              type="button"
              onClick={() => window.dispatchEvent(new Event("haru:open-chats"))}
              className="px-2 py-1.5 pointer-coarse:min-h-11 text-left text-xs text-muted hover:text-fg"
            >
              모두 보기
            </button>
          </>
        )}
      </section>
    </div>
  );
}
