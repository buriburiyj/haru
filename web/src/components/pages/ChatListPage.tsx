import { useState } from "react";
import PageShell from "./PageShell";

type Kind = "채팅" | "Code" | "Cowork";
type Chat = { id: number; title: string; kind: Kind; ago: string; archived?: boolean };

const CHATS: Chat[] = [
  { id: 1, title: "여행 일정 정리", kind: "채팅", ago: "방금" },
  { id: 2, title: "로그인 버그 수정", kind: "Code", ago: "3시간 전" },
  { id: 3, title: "주간 보고서 초안", kind: "Cowork", ago: "3시간 전" },
  { id: 4, title: "레시피 추천", kind: "채팅", ago: "어제" },
  { id: 5, title: "API 서버 리팩터링", kind: "Code", ago: "어제" },
  { id: 6, title: "회의록 요약", kind: "Cowork", ago: "3일 전" },
  { id: 7, title: "영어 이메일 번역", kind: "채팅", ago: "3일 전", archived: true },
  { id: 8, title: "독서 목록 정리", kind: "채팅", ago: "3일 전", archived: true },
];

const FILTERS = ["전체", "채팅", "Code", "Cowork", "즉시 보관"] as const;
type Filter = (typeof FILTERS)[number];

export default function ChatListPage({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("전체");
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [confirming, setConfirming] = useState(false);

  const rows = CHATS.filter((c) => {
    if (filter === "즉시 보관" ? !c.archived : filter !== "전체" && c.kind !== filter) return false;
    return c.title.toLowerCase().includes(query.trim().toLowerCase());
  });

  const toggleSelecting = () => {
    setSelecting((v) => !v);
    setSelected([]);
    setConfirming(false);
  };
  const toggleRow = (id: number) => {
    setConfirming(false);
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  };
  const newChat = () => {
    window.dispatchEvent(new Event("haru:new-chat"));
    onClose();
  };

  const actions = (
    <>
      <button
        type="button"
        onClick={toggleSelecting}
        className={`min-h-11 rounded-lg border border-line px-3 text-sm ${selecting ? "bg-surface-2 text-fg" : "text-muted hover:text-fg"}`}
      >
        선택
      </button>
      <button type="button" onClick={newChat} className="min-h-11 rounded-lg bg-accent px-3 text-sm text-accent-fg">
        새로 만들기
      </button>
    </>
  );

  return (
    <PageShell title="채팅 및 작업" onClose={onClose} actions={actions}>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="채팅 검색"
        className="min-h-11 w-full rounded-lg border border-line bg-surface px-3 text-fg placeholder:text-muted"
      />
      <div className="mt-3 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`min-h-11 rounded-full border border-line px-4 text-sm ${filter === f ? "bg-accent text-accent-fg" : "bg-surface text-muted hover:text-fg"}`}
          >
            {f}
          </button>
        ))}
      </div>
      <ul className={`mt-4 divide-y divide-line ${selecting ? "pb-24" : ""}`}>
        {rows.length === 0 && <li className="py-8 text-center text-muted">채팅이 없습니다.</li>}
        {rows.map((c) => (
          <li key={c.id}>
            <div
              role={selecting ? "button" : undefined}
              onClick={selecting ? () => toggleRow(c.id) : undefined}
              className="flex min-h-11 items-center gap-3 py-3"
            >
              {selecting && (
                <input
                  type="checkbox"
                  checked={selected.includes(c.id)}
                  onChange={() => toggleRow(c.id)}
                  onClick={(e) => e.stopPropagation()}
                  aria-label={`${c.title} 선택`}
                  className="size-5 shrink-0 accent-accent"
                />
              )}
              <span className="min-w-0 flex-1 truncate">{c.title}</span>
              <span className="shrink-0 text-sm text-muted">{c.ago}</span>
            </div>
          </li>
        ))}
      </ul>
      {selecting && (
        <div className="fixed inset-x-0 bottom-0 z-50 border-t border-line bg-surface px-4 py-3 md:left-64">
          <div className="mx-auto flex w-full max-w-3xl items-center gap-3">
            <span className="mr-auto text-sm">{selected.length}개 선택</span>
            {confirming && <span className="text-sm text-danger">삭제하려면 한 번 더 누르세요</span>}
            <button
              type="button"
              disabled={selected.length === 0}
              onClick={() => setConfirming(true)}
              className="min-h-11 rounded-lg border border-line px-4 text-sm text-danger disabled:opacity-50"
            >
              삭제
            </button>
          </div>
        </div>
      )}
    </PageShell>
  );
}
