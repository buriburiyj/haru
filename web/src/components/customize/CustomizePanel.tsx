import { useMemo, useState } from "react";
import {
  EXPLORE_CONNECTORS,
  EXPLORE_PLUGINS,
  EXPLORE_SKILLS,
  KIND_LABEL,
  KIND_NOUN,
  MY_CONNECTORS,
  MY_PLUGINS,
  MY_SKILLS,
  type ConnectorItem,
  type Kind,
  type PluginItem,
  type SkillItem,
} from "./sample";

const KINDS: Kind[] = ["skills", "connectors", "plugins"];
type Sort = "name" | "recent";

const tabCls = (on: boolean) =>
  `rounded-lg px-3 py-1.5 text-sm ${on ? "bg-surface-2 text-fg" : "text-muted hover:text-fg"}`;

function RowMenu({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        aria-label="더 보기"
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        className="rounded-md px-2 py-1 text-muted hover:bg-surface-2 hover:text-fg"
      >
        ⋯
      </button>
      {open && (
        <div className="absolute right-0 top-full z-10 mt-1 flex min-w-32 flex-col rounded-xl border border-line bg-surface p-1 shadow-lg">
          {items.map((t) => (
            <button key={t} type="button" className="rounded-lg px-2 py-1.5 text-left text-sm text-fg hover:bg-surface-2">
              {t}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyCard({ kind, onBrowse }: { kind: Kind; onBrowse: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-line bg-surface p-8 text-center">
      <p className="text-sm text-fg">첫 번째 {KIND_NOUN[kind]} 추가하기</p>
      <div className="flex gap-2">
        <button type="button" className="rounded-lg bg-accent px-3 py-1.5 text-sm text-accent-fg">
          + 추가
        </button>
        <button type="button" onClick={onBrowse} className="rounded-lg border border-line px-3 py-1.5 text-sm text-fg">
          둘러보기
        </button>
      </div>
    </div>
  );
}

function SkillList({ items }: { items: SkillItem[] }) {
  return (
    <ul className="flex flex-col">
      {items.map((s) => (
        <li key={s.name} className="flex items-center gap-3 border-b border-line py-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <span className="text-sm text-fg">{s.name}</span>
              <span className="text-xs text-muted">{s.provider}</span>
            </div>
            <p className="truncate text-xs text-muted">{s.description}</p>
          </div>
          <span className="hidden text-xs text-muted sm:block">{s.date}</span>
          <RowMenu items={["보기", "이름 바꾸기", "삭제"]} />
        </li>
      ))}
    </ul>
  );
}

function ConnectorTable({ items }: { items: ConnectorItem[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-80 text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th className="py-2 font-normal">이름</th>
            <th className="py-2 font-normal">유형</th>
            <th className="py-2 text-right font-normal">상태</th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.name} className="border-b border-line">
              <td className="py-3 text-fg">{c.name}</td>
              <td className="py-3 text-muted">{c.type}</td>
              <td className="py-3 text-right">
                {c.connected ? (
                  <span className="text-accent" aria-label="연결됨">
                    ✓
                  </span>
                ) : (
                  <button type="button" className="rounded-lg border border-line px-3 py-1 text-xs text-fg hover:bg-surface-2">
                    연결
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PluginList({ items }: { items: PluginItem[] }) {
  return (
    <ul className="flex flex-col">
      {items.map((p) => (
        <li key={p.name} className="flex items-center gap-3 border-b border-line py-3">
          <div className="min-w-0 flex-1">
            <div className="text-sm text-fg">{p.name}</div>
            <p className="truncate text-xs text-muted">{p.description}</p>
          </div>
          <span className="text-xs text-muted">{p.includes}</span>
          <RowMenu items={["보기", "한 번에 지우기"]} />
        </li>
      ))}
    </ul>
  );
}

type Card = { name: string; description: string; by: string; added: boolean };

function ExploreGrid({ cards }: { cards: Card[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {cards.map((c) => (
        <div key={c.name} className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-fg">{c.name}</span>
            {c.added && (
              <span className="text-accent" aria-label="연결됨">
                ✓
              </span>
            )}
          </div>
          <p className="text-xs text-muted">{c.description}</p>
          <div className="mt-1 flex items-center justify-between">
            <span className="text-xs text-muted">{c.by}</span>
            <div className="flex gap-1">
              <button type="button" className="rounded-lg border border-line px-2.5 py-1 text-xs text-fg hover:bg-surface-2">
                체험
              </button>
              {!c.added && (
                <button type="button" aria-label="추가" className="rounded-lg bg-accent px-2.5 py-1 text-xs text-accent-fg">
                  +
                </button>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function exploreCards(kind: Kind): Card[] {
  if (kind === "skills") return EXPLORE_SKILLS.map((s) => ({ name: s.name, description: s.description, by: s.provider, added: false }));
  if (kind === "connectors") return EXPLORE_CONNECTORS.map((c) => ({ name: c.name, description: c.description, by: c.type === "웹" ? "웹" : "로컬", added: c.connected }));
  return EXPLORE_PLUGINS.map((p) => ({ name: p.name, description: p.description, by: p.includes, added: false }));
}

/**
 * One screen for Skills / Connectors / Plugins, used by the sidebar "사용자 지정" dialog and by Settings.
 * Pass onKindChange to show the [Skills|커넥터|플러그인] tabs; otherwise `kind` is fixed by the caller.
 */
export default function CustomizePanel({ kind, onKindChange, hideTitle = false }: { kind: Kind; onKindChange?: (k: Kind) => void; hideTitle?: boolean }) {
  const [view, setView] = useState<"mine" | "explore">("mine");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("name");
  const [addOpen, setAddOpen] = useState(false);

  const q = query.trim().toLowerCase();
  const match = (s: string) => s.toLowerCase().includes(q);
  const byName = <T extends { name: string }>(a: T[]) => (sort === "name" ? [...a].sort((x, y) => x.name.localeCompare(y.name)) : a);

  const mine = useMemo(() => {
    if (kind === "skills") return byName(MY_SKILLS.filter((s) => match(s.name + s.description)));
    if (kind === "connectors") return byName(MY_CONNECTORS.filter((c) => match(c.name + c.description)));
    return byName(MY_PLUGINS.filter((p) => match(p.name + p.description)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, q, sort]);
  const cards = exploreCards(kind).filter((c) => match(c.name + c.description));
  const totalMine = kind === "skills" ? MY_SKILLS.length : kind === "connectors" ? MY_CONNECTORS.length : MY_PLUGINS.length;

  return (
    <div className="flex min-w-0 flex-col gap-4">
      {onKindChange && (
        <div className="flex gap-1">
          {KINDS.map((k) => (
            <button key={k} type="button" onClick={() => onKindChange(k)} className={tabCls(k === kind)}>
              {KIND_LABEL[k]}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        {hideTitle ? <span className="mr-auto" /> : <h2 className="mr-auto text-lg font-semibold text-fg">{KIND_LABEL[kind]}</h2>}
        <div className="relative">
          <button
            type="button"
            onClick={() => setAddOpen((v) => !v)}
            className="rounded-lg bg-accent px-3 py-1.5 text-sm text-accent-fg"
          >
            + 추가 ▾
          </button>
          {addOpen && (
            <div className="absolute right-0 top-full z-10 mt-1 flex min-w-40 flex-col rounded-xl border border-line bg-surface p-1 shadow-lg">
              {(kind === "connectors" ? ["웹 커넥터 추가", "로컬 커넥터 추가"] : kind === "skills" ? ["직접 만들기", "URL로 가져오기", "파일 올리기"] : ["URL로 설치", "파일 올리기"]).map((t) => (
                <button key={t} type="button" onClick={() => setAddOpen(false)} className="rounded-lg px-2 py-1.5 text-left text-sm text-fg hover:bg-surface-2">
                  {t}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1">
          <button type="button" onClick={() => setView("mine")} className={tabCls(view === "mine")}>
            내 항목
          </button>
          <button type="button" onClick={() => setView("explore")} className={tabCls(view === "explore")}>
            탐색
          </button>
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="검색"
          aria-label="검색"
          className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-sm text-fg outline-none placeholder:text-muted focus:border-accent"
        />
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as Sort)}
          aria-label="정렬"
          className="rounded-lg border border-line bg-surface px-2 py-1.5 text-sm text-fg"
        >
          <option value="name">이름순</option>
          <option value="recent">최근순</option>
        </select>
      </div>

      {view === "explore" ? (
        cards.length ? <ExploreGrid cards={cards} /> : <p className="text-sm text-muted">결과가 없습니다.</p>
      ) : totalMine === 0 ? (
        <EmptyCard kind={kind} onBrowse={() => setView("explore")} />
      ) : mine.length === 0 ? (
        <p className="text-sm text-muted">결과가 없습니다.</p>
      ) : kind === "skills" ? (
        <SkillList items={mine as SkillItem[]} />
      ) : kind === "connectors" ? (
        <ConnectorTable items={mine as ConnectorItem[]} />
      ) : (
        <PluginList items={mine as PluginItem[]} />
      )}
    </div>
  );
}
