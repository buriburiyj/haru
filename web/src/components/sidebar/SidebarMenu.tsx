import { useState } from "react";
import type { ReactNode } from "react";
import type { ChatHistoryItem } from "../../types";
import {
  ArtifactIcon,
  ChevronDownIcon,
  CustomizeIcon,
  FolderIcon,
  PlusIcon,
  SearchIcon,
} from "./icons";

const itemCls =
  "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm text-fg hover:bg-surface-2";

function MenuItem({ icon, label, onClick }: { icon: ReactNode; label: string; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} className={itemCls}>
      <span className="text-muted">{icon}</span>
      {label}
    </button>
  );
}

export default function SidebarMenu({ recent, onNew }: { recent: ChatHistoryItem[]; onNew: () => void }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
      <nav className="flex flex-col gap-0.5">
        <MenuItem icon={<PlusIcon />} label="새로 만들기" onClick={onNew} />
        <MenuItem icon={<SearchIcon />} label="검색" onClick={() => window.dispatchEvent(new Event("haru:open-search"))} />
        <div className="group/proj relative">
          <MenuItem icon={<FolderIcon />} label="프로젝트" onClick={() => window.dispatchEvent(new Event("haru:open-projects"))} />
          <button
            type="button"
            aria-label="새 프로젝트"
            title="새 프로젝트"
            onClick={() => window.dispatchEvent(new Event("haru:new-project"))}
            className="absolute right-1 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-muted opacity-0 hover:bg-surface hover:text-fg focus:opacity-100 group-hover/proj:opacity-100 [@media(pointer:coarse)]:opacity-100"
          >
            +
          </button>
        </div>
        <MenuItem icon={<ArtifactIcon />} label="아티팩트" onClick={() => window.dispatchEvent(new Event("haru:open-artifacts"))} />
        <MenuItem icon={<CustomizeIcon />} label="사용자 지정" onClick={() => window.dispatchEvent(new Event("haru:open-customize"))} />
      </nav>
      <section className="flex flex-col gap-0.5">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-1 px-2 py-1 text-xs text-muted hover:text-fg"
        >
          채팅 및 작업
          <span className={expanded ? "" : "-rotate-90"}>
            <ChevronDownIcon />
          </span>
        </button>
        {expanded && (
          <>
            {recent.slice(0, 7).map((c) => (
              <button key={c.id} type="button" className={itemCls + " justify-between"}>
                <span className="truncate">{c.title}</span>
                <span className="shrink-0 text-xs text-muted">{c.when}</span>
              </button>
            ))}
            <button
              type="button"
              onClick={() => window.dispatchEvent(new Event("haru:open-chats"))}
              className="px-2 py-1.5 text-left text-xs text-muted hover:text-fg"
            >
              모두 보기
            </button>
          </>
        )}
      </section>
    </div>
  );
}
