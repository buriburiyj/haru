import { useEffect, useRef, useState } from "react";
import { Button, Chip, IconButton } from "../ui";
import type { ChatRow } from "../chat/dataTypes";

const TABS = ["전체", "아티팩트", "채팅", "프로젝트", "세션", "작업", "예약됨"];
const ACTIVE_TABS = ["전체", "채팅"];

type Props = {
  chats: ChatRow[];
  searchChats: (q: string) => Promise<ChatRow[]>;
  onOpenChat: (id: string) => void;
  onClose: () => void;
};

export default function SearchDialog({ chats, searchChats, onOpenChat, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState(TABS[0]);
  const [results, setResults] = useState<ChatRow[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [hi, setHi] = useState(0);
  const seq = useRef(0);

  const q = query.trim();
  const rows = q ? results : chats.slice(0, 8);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    const id = ++seq.current;
    setHi(0);
    if (!q) {
      setStatus("idle");
      setResults([]);
      return;
    }
    setStatus("loading");
    const t = window.setTimeout(() => {
      searchChats(q).then(
        (r) => {
          if (id !== seq.current) return;
          setResults(r);
          setStatus("done");
        },
        () => {
          if (id !== seq.current) return;
          setStatus("error");
        },
      );
    }, 250);
    return () => window.clearTimeout(t);
  }, [q, searchChats]);

  const open = (id: string) => {
    onOpenChat(id);
    onClose();
  };
  const onInputKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHi((h) => Math.min(h + 1, Math.max(rows.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHi((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter" && rows[hi] && !(q && status !== "done")) {
      e.preventDefault();
      open(rows[hi].id);
    }
  };

  const message =
    q && status === "loading" ? "검색 중…"
    : q && status === "error" ? "검색하지 못했습니다"
    : rows.length === 0 ? "결과가 없습니다"
    : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-center bg-fg/40 md:items-start md:p-6 md:pt-24"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-label="검색"
        className="flex h-full w-full flex-col overflow-hidden bg-bg text-fg md:h-auto md:max-h-160 md:max-w-xl md:rounded-card md:border md:border-line"
      >
        <div className="flex items-center gap-2 border-b border-line p-3">
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKey}
            placeholder="검색"
            className="min-w-0 flex-1 bg-transparent px-1 text-base text-fg outline-none placeholder:text-muted"
          />
          <IconButton label="닫기" onClick={onClose} className="md:hidden">
            ✕
          </IconButton>
        </div>
        <div className="flex gap-1 overflow-x-auto border-b border-line p-2">
          {TABS.map((t) => {
            const on = ACTIVE_TABS.includes(t);
            return (
              <Chip
                key={t}
                selected={tab === t}
                disabled={!on}
                title={on ? undefined : "준비 중"}
                onClick={() => on && setTab(t)}
                className={"shrink-0" + (on ? "" : " text-muted opacity-60")}
              >
                {t}
              </Chip>
            );
          })}
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {!q && rows.length > 0 && <div className="px-2 py-1 text-xs text-muted">최근 항목</div>}
          {message && <div className="px-2 py-6 text-center text-sm text-muted">{message}</div>}
          {!(q && status !== "done") &&
            rows.map((r, i) => (
              <Button
                key={r.id}
                variant="ghost"
                onClick={() => open(r.id)}
                onMouseMove={() => setHi(i)}
                className={"w-full justify-between gap-3 px-2 text-left font-normal " + (i === hi ? "bg-surface-2" : "")}
              >
                <span className="flex min-w-0 flex-col">
                  <span className="truncate">{r.title}</span>
                  {q && r.preview && <span className="truncate text-xs text-muted">{r.preview}</span>}
                </span>
                <span className="shrink-0 text-xs text-muted">{r.when}</span>
              </Button>
            ))}
        </div>
        <div className="hidden items-center gap-4 border-t border-line bg-surface px-4 py-2 text-xs text-muted md:flex">
          <span>↑↓ 이동</span>
          <span>↵ 열기</span>
          <span>Tab 탭 전환</span>
          <span className="ml-auto">Esc 닫기</span>
        </div>
      </div>
    </div>
  );
}
