import { useEffect, useMemo, useState } from "react";
import CustomizePanel from "../customize/CustomizePanel";
import type { Kind } from "../customize/sample";

type Row =
  | { label: string; kind: "seg"; options: string[]; initial?: number; theme?: boolean }
  | { label: string; kind: "toggle"; on?: boolean }
  | { label: string; kind: "value"; value: string }
  | { label: string; kind: "button"; text: string; danger?: boolean };

interface Page {
  id: string;
  title: string;
  rows: Row[];
  empty?: string;
}

const PAGES: Page[] = [
  {
    id: "general",
    title: "일반",
    rows: [
      { label: "테마", kind: "seg", options: ["시스템", "라이트", "다크"], theme: true },
      { label: "인터페이스 글꼴", kind: "seg", options: ["기본", "시스템"] },
      { label: "응답 글꼴", kind: "seg", options: ["기본", "시스템", "고정폭"] },
      { label: "대화 글자 크기", kind: "seg", options: ["작게", "보통", "크게"], initial: 1 },
      { label: "대화 너비", kind: "seg", options: ["좁게", "기본", "넓게"], initial: 1 },
      { label: "모션", kind: "seg", options: ["시스템", "줄이기", "켜기"] },
      { label: "받아쓰기 언어", kind: "value", value: "한국어" },
      { label: "알림: 응답 완료", kind: "toggle", on: true },
    ],
  },
  {
    id: "account",
    title: "계정",
    rows: [
      { label: "이름", kind: "value", value: "준" },
      { label: "호칭", kind: "value", value: "준 님" },
      { label: "패스키 관리", kind: "button", text: "관리" },
      { label: "로그아웃", kind: "button", text: "로그아웃", danger: true },
    ],
  },
  {
    id: "privacy",
    title: "개인정보",
    rows: [
      { label: "위치(도시) 사용", kind: "toggle" },
      { label: "데이터 내보내기", kind: "button", text: "내보내기" },
      { label: "공유 링크", kind: "button", text: "관리" },
      { label: "업로드 파일", kind: "button", text: "관리" },
    ],
  },
  {
    id: "features",
    title: "기능",
    rows: [
      { label: "도구 로드 방식", kind: "seg", options: ["필요할 때", "항상"] },
      { label: "커넥터 제안", kind: "toggle", on: true },
      { label: "아티팩트", kind: "toggle", on: true },
      { label: "채팅 안 시각화", kind: "toggle", on: true },
      { label: "코드 실행 및 파일 생성", kind: "toggle", on: true },
    ],
  },
  {
    id: "memory",
    title: "메모리",
    rows: [
      { label: "메모리 생성", kind: "toggle", on: true },
      { label: "기억 목록", kind: "button", text: "보기" },
    ],
  },
  {
    id: "recap",
    title: "회고",
    rows: [],
    empty: "메모리를 켜면 주간 돌아보기가 여기에 표시됩니다.",
  },
  {
    id: "focus",
    title: "시간 및 집중",
    rows: [
      { label: "휴식 알림", kind: "toggle" },
      { label: "방해 금지 요일", kind: "value", value: "토, 일" },
      { label: "방해 금지 시간", kind: "value", value: "22:00 - 07:00" },
    ],
  },
  {
    id: "code",
    title: "Code",
    rows: [
      { label: "세션 상태 분류", kind: "value", value: "막힘 / 검토 대기 / 완료" },
      { label: "코드 테마", kind: "seg", options: ["라이트", "다크"] },
      { label: "자동 수락 모드 기본값", kind: "toggle" },
    ],
  },
  {
    id: "system",
    title: "시스템",
    rows: [
      { label: "버전", kind: "value", value: "0.1.0" },
      { label: "로그인 시 실행", kind: "toggle" },
      { label: "빠른 실행", kind: "value", value: "⌥ ⌥" },
      { label: "받아쓰기", kind: "value", value: "⌘ D" },
      { label: "메뉴 막대", kind: "toggle", on: true },
      { label: "저장 공간", kind: "value", value: "128 MB" },
    ],
  },
  {
    id: "developer",
    title: "개발자",
    rows: [
      { label: "로컬 MCP 서버", kind: "value", value: "2개" },
      { label: "구성 편집", kind: "button", text: "열기" },
      { label: "상태", kind: "value", value: "실행 중" },
    ],
  },
  {
    id: "skills",
    title: "Skills",
    rows: [
      { label: "skill-creator", kind: "value", value: "기본 제공" },
      { label: "morning (아침 브리핑)", kind: "value", value: "기본 제공" },
      { label: "import-memory", kind: "value", value: "기본 제공" },
    ],
  },
  {
    id: "connectors",
    title: "커넥터",
    rows: [
      { label: "Hostless", kind: "value", value: "웹 · 연결됨" },
      { label: "Filesystem", kind: "value", value: "로컬 · 연결됨" },
      { label: "GitHub", kind: "button", text: "연결" },
    ],
  },
  {
    id: "plugins",
    title: "플러그인",
    rows: [],
    empty: "첫 번째 플러그인 추가하기",
  },
];

const GROUPS: { name: string; ids: string[]; macOnly?: boolean }[] = [
  { name: "환경설정", ids: ["general", "account", "privacy", "features", "memory", "recap", "focus", "code"] },
  { name: "이 기기", ids: ["system", "developer"], macOnly: true },
  { name: "사용자 지정", ids: ["skills", "connectors", "plugins"] },
];

const THEME_VALUES = [undefined, "light", "dark"] as const;

function Control({ row }: { row: Row }) {
  const [sel, setSel] = useState(row.kind === "seg" ? row.initial ?? 0 : 0);
  const [on, setOn] = useState(row.kind === "toggle" ? !!row.on : false);

  if (row.kind === "seg") {
    return (
      <div className="inline-flex rounded-lg border border-line bg-surface p-0.5">
        {row.options.map((o, i) => (
          <button
            key={o}
            type="button"
            onClick={() => {
              setSel(i);
              if (row.theme) {
                const v = THEME_VALUES[i];
                if (v) document.documentElement.dataset.theme = v;
                else delete document.documentElement.dataset.theme;
              }
            }}
            className={`rounded-md px-3 py-1 text-sm ${
              sel === i ? "bg-accent text-accent-fg" : "text-muted"
            }`}
          >
            {o}
          </button>
        ))}
      </div>
    );
  }
  if (row.kind === "toggle") {
    return (
      <button
        type="button"
        role="switch"
        aria-checked={on}
        onClick={() => setOn(!on)}
        className={`relative h-6 w-10 rounded-full border border-line ${on ? "bg-accent" : "bg-surface-2"}`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-bg ${on ? "left-5" : "left-0.5"}`}
        />
      </button>
    );
  }
  if (row.kind === "value") return <span className="text-sm text-muted">{row.value}</span>;
  return (
    <button
      type="button"
      className={`rounded-lg border border-line bg-surface px-3 py-1 text-sm ${
        row.danger ? "text-danger" : "text-fg"
      }`}
    >
      {row.text}
    </button>
  );
}

export default function SettingsDialog({
  onClose,
  isMacApp = false,
}: {
  onClose: () => void;
  isMacApp?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [current, setCurrent] = useState("general");
  // On phone: list first, detail after selection.
  const [detailOpen, setDetailOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const groups = useMemo(
    () =>
      GROUPS.filter((g) => !g.macOnly || isMacApp)
        .map((g) => ({
          ...g,
          pages: g.ids
            .map((id) => PAGES.find((p) => p.id === id)!)
            .filter((p) => p.title.toLowerCase().includes(query.trim().toLowerCase())),
        }))
        .filter((g) => g.pages.length > 0),
    [isMacApp, query],
  );

  const page = PAGES.find((p) => p.id === current) ?? PAGES[0];

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-center bg-fg/40 md:items-center md:p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-label="설정"
        className="flex h-full w-full overflow-hidden bg-bg text-fg md:h-[min(40rem,100%)] md:max-w-3xl md:rounded-2xl md:border md:border-line"
      >
        <nav
          className={`${detailOpen ? "hidden" : "flex"} w-full flex-col gap-3 overflow-y-auto border-line bg-surface p-3 md:flex md:w-56 md:shrink-0 md:border-r`}
        >
          <div className="flex items-center gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="설정 검색"
              className="min-w-0 flex-1 rounded-lg border border-line bg-bg px-3 py-1.5 text-sm text-fg outline-none placeholder:text-muted"
            />
            <button type="button" onClick={onClose} aria-label="닫기" className="px-2 text-muted md:hidden">
              ✕
            </button>
          </div>
          {groups.map((g) => (
            <div key={g.name} className="flex flex-col gap-0.5">
              <div className="px-2 py-1 text-xs text-muted">{g.name}</div>
              {g.pages.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => {
                    setCurrent(p.id);
                    setDetailOpen(true);
                  }}
                  className={`rounded-lg px-2 py-1.5 text-left text-sm ${
                    current === p.id ? "bg-surface-2 text-fg" : "text-fg"
                  }`}
                >
                  {p.title}
                </button>
              ))}
            </div>
          ))}
        </nav>

        <section
          className={`${detailOpen ? "flex" : "hidden"} min-w-0 flex-1 flex-col overflow-y-auto p-5 md:flex`}
        >
          <div className="mb-4 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setDetailOpen(false)}
              aria-label="뒤로"
              className="px-1 text-muted md:hidden"
            >
              ←
            </button>
            <h2 className="flex-1 text-lg font-semibold">{page.title}</h2>
            <button type="button" onClick={onClose} aria-label="닫기" className="hidden px-2 text-muted md:block">
              ✕
            </button>
          </div>
          {(page.id === "skills" || page.id === "connectors" || page.id === "plugins") && (
            <CustomizePanel kind={page.id as Kind} hideTitle />
          )}
          {page.id !== "skills" && page.id !== "connectors" && page.id !== "plugins" && page.rows.length === 0 && page.empty && (
            <div className="rounded-xl border border-line bg-surface p-6 text-center text-sm text-muted">
              {page.empty}
            </div>
          )}
          <div className="flex flex-col">
            {page.id !== "skills" && page.id !== "connectors" && page.id !== "plugins" && page.rows.map((r) => (
              <div
                key={page.id + r.label}
                className="flex items-center justify-between gap-4 border-b border-line py-3"
              >
                <span className="text-sm">{r.label}</span>
                <Control row={r} />
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
