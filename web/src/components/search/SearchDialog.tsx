import { useEffect, useState } from "react";
import { Button, Chip, IconButton } from "../ui";

const TABS = ["전체", "아티팩트", "채팅", "프로젝트", "세션", "작업", "예약됨"];

const SECTIONS: { name: string; rows: { title: string; meta: string }[] }[] = [
  {
    name: "주의 필요",
    rows: [{ title: "배포 스크립트 점검", meta: "세션 · 검토 대기" }],
  },
  {
    name: "최근 항목",
    rows: [
      { title: "주간 회고 정리", meta: "채팅 · 어제" },
      { title: "Haru 웹 UI", meta: "프로젝트 · 2일 전" },
      { title: "요금 비교표", meta: "아티팩트 · 3일 전" },
    ],
  },
  {
    name: "작업",
    rows: [
      { title: "아침 브리핑", meta: "예약됨 · 매일 07:30" },
      { title: "새 채팅 시작", meta: "작업" },
    ],
  },
];

export default function SearchDialog({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState(TABS[0]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const q = query.trim().toLowerCase();

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
            placeholder="검색"
            className="min-w-0 flex-1 bg-transparent px-1 text-base text-fg outline-none placeholder:text-muted"
          />
          <IconButton label="닫기" onClick={onClose} className="md:hidden">
            ✕
          </IconButton>
        </div>
        <div className="flex gap-1 overflow-x-auto border-b border-line p-2">
          {TABS.map((t) => (
            <Chip key={t} selected={tab === t} onClick={() => setTab(t)} className="shrink-0">
              {t}
            </Chip>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {SECTIONS.map((s) => {
            const rows = s.rows.filter(
              (r) =>
                (!q || r.title.toLowerCase().includes(q)) &&
                (tab === "전체" || r.meta.includes(tab)),
            );
            if (rows.length === 0) return null;
            return (
              <div key={s.name} className="mb-2">
                <div className="px-2 py-1 text-xs text-muted">{s.name}</div>
                {rows.map((r) => (
                  <Button key={r.title} variant="ghost" className="w-full justify-between px-2 text-left font-normal">
                    <span className="truncate">{r.title}</span>
                    <span className="shrink-0 text-xs text-muted">{r.meta}</span>
                  </Button>
                ))}
              </div>
            );
          })}
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
