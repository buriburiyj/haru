import { useState } from "react";
import PageShell from "./PageShell";
import { Button, Card, Tabs } from "../ui";

type Owner = "mine" | "shared";
type Item = { id: number; title: string; type: string; date: string; owner: Owner };

const TABS = [
  { key: "all", label: "전체" },
  { key: "mine", label: "내 항목" },
  { key: "shared", label: "공유받음" },
] as const;
type Tab = (typeof TABS)[number]["key"];

const TEMPLATES = [
  { name: "문서", desc: "보고서, 메모, 기획서를 글로 정리해요." },
  { name: "슬라이드", desc: "발표 자료를 장표 단위로 만들어요." },
  { name: "디자인", desc: "화면과 레이아웃 시안을 그려요." },
];

const ITEMS: Item[] = [
  { id: 1, title: "여행 일정표", type: "문서", date: "방금", owner: "mine" },
  { id: 2, title: "분기 발표 자료", type: "슬라이드", date: "어제", owner: "mine" },
  { id: 3, title: "랜딩 페이지 시안", type: "디자인", date: "3일 전", owner: "shared" },
  { id: 4, title: "팀 회의 노트", type: "문서", date: "3일 전", owner: "shared" },
];

export default function ArtifactsPage({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("all");
  const items = ITEMS.filter((i) => tab === "all" || i.owner === tab);

  return (
    <PageShell title="아티팩트" onClose={onClose}>
      <Tabs value={tab} options={TABS.map((t) => ({ id: t.key, label: t.label }))} onChange={setTab} />

      <h2 className="mt-6 text-sm font-semibold text-muted">템플릿</h2>
      <div className="mt-2 grid gap-3 sm:grid-cols-3">
        {TEMPLATES.map((t) => (
          <Card key={t.name} className="flex flex-col gap-2">
            <div className="font-semibold">{t.name}</div>
            <p className="flex-1 text-sm text-muted">{t.desc}</p>
            <Button variant="primary">만들기</Button>
          </Card>
        ))}
      </div>

      <h2 className="mt-6 text-sm font-semibold text-muted">내 아티팩트</h2>
      {items.length === 0 ? (
        <p className="py-8 text-center text-muted">아직 아티팩트가 없습니다.</p>
      ) : (
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          {items.map((i) => (
            <Card key={i.id} className="bg-surface-2">
              <div className="truncate font-medium">{i.title}</div>
              <div className="mt-1 text-sm text-muted">
                {i.type} · {i.date}
              </div>
            </Card>
          ))}
        </div>
      )}
    </PageShell>
  );
}
