import { useState } from "react";
import {
  FONTS,
  FONT_SIZES,
  THEMES,
  getFont,
  getFontSize,
  getTheme,
  setFont,
  setFontSize,
  setTheme,
  type Font,
  type FontSize,
  type Theme,
} from "../settings/appearance";
import { Button, Card, Chip, Dialog, IconButton, Input, Menu, MenuDivider, MenuItem, Reply, SubMenu, Tabs, Textarea, UserBubble } from "./index";

// Design check screen: open <site>/haru/?demo=ui . No login, no server calls, no secrets. Sample text only.

const THEME_LABEL: Record<Theme, string> = { system: "시스템", light: "라이트", dark: "다크" };
const FONT_LABEL: Record<Font, string> = { default: "기본 (답변 명조)", gothic: "고딕", system: "시스템" };
const SIZE_LABEL: Record<FontSize, string> = { small: "작게", medium: "보통", large: "크게" };

const SWATCHES = [
  ["accent", "var(--haru-accent)"],
  ["accent-hover", "var(--haru-accent-hover)"],
  ["accent-strong", "var(--haru-accent-strong)"],
  ["bg", "var(--haru-bg)"],
  ["surface", "var(--haru-surface)"],
  ["surface-2", "var(--haru-surface-2)"],
  ["line", "var(--haru-border)"],
  ["fg", "var(--haru-fg)"],
  ["fg-2", "var(--haru-fg-2)"],
  ["muted", "var(--haru-muted)"],
  ["danger", "var(--haru-danger)"],
] as const;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="border-b border-line pb-1 text-sm font-semibold text-muted">{title}</h2>
      {children}
    </section>
  );
}

function Choice<T extends string>({ label, value, ids, text, onPick }: { label: string; value: T; ids: T[]; text: Record<T, string>; onPick: (v: T) => void }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-muted">{label}</span>
      <Tabs value={value} options={ids.map((id) => ({ id, label: text[id] }))} onChange={onPick} label={label} />
    </div>
  );
}

export default function UiDemo() {
  const [theme, setThemeState] = useState<Theme>(getTheme);
  const [font, setFontState] = useState<Font>(getFont);
  const [size, setSizeState] = useState<FontSize>(getFontSize);
  const [tab, setTab] = useState("chat");
  const [chip, setChip] = useState("all");
  const [menu, setMenu] = useState(false);
  const [dialog, setDialog] = useState(false);
  const [model, setModel] = useState(0);
  const [effort, setEffort] = useState(1);
  const [web, setWeb] = useState(true);
  const [chipMenu, setChipMenu] = useState(false);

  return (
    <div className="h-full overflow-y-auto bg-bg text-fg">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-8 px-4 py-6">
        <header className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold">Haru 디자인 확인</h1>
          <p className="text-sm text-muted">로그인 없이 보이는 확인용 화면입니다. 서버와 통신하지 않습니다.</p>
        </header>

        <div className="sticky top-0 z-20 -mx-4 flex flex-col gap-3 border-b border-line bg-bg/95 px-4 py-3 backdrop-blur-md">
          <Choice label="테마" value={theme} ids={THEMES} text={THEME_LABEL} onPick={(v) => { setThemeState(v); setTheme(v); }} />
          <Choice label="글꼴" value={font} ids={FONTS} text={FONT_LABEL} onPick={(v) => { setFontState(v); setFont(v); }} />
          <Choice label="글자 크기" value={size} ids={FONT_SIZES} text={SIZE_LABEL} onPick={(v) => { setSizeState(v); setFontSize(v); }} />
        </div>

        <Section title="답변 예시 (글꼴 확인)">
          <UserBubble>이번 주 일정을 정리해 주세요. Meeting at 3:30 PM, 예산은 1,250,000원입니다.</UserBubble>
          <Reply>
            <p>
              네, 정리했습니다. 이번 주는 월요일에 기획 회의가 있고, 수요일에는 디자인 검토가 잡혀 있습니다. 한글 문단은 마루 부리로,
              영어와 숫자는 Source Serif 4로 보입니다. 글자 사이가 답답하지 않은지, 줄 간격이 편안한지 봐 주세요.
            </p>
            <p className="mt-3">
              Version 2.5 of the plan ships on 2026-11-20, and the budget is $1,250.00. 한영이 섞인 문장도 자연스럽게 이어져야 합니다:
              Haru는 하루를 돕는 비서이고, API는 150MB 이하의 메모리로 동작합니다.
            </p>
            <ul className="mt-3 list-disc pl-6">
              <li>목록 첫 번째 항목입니다.</li>
              <li>Second item with 123 numbers.</li>
            </ul>
            <pre className="mt-3 overflow-x-auto rounded-card border border-line bg-surface p-4 text-sm" style={{ fontFamily: "var(--haru-font-mono)", lineHeight: 1.6 }}>
{`function total(items: number[]) {
  // 합계를 계산합니다
  return items.reduce((a, b) => a + b, 0);
}`}
            </pre>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-72 border-collapse text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-muted">
                    <th className="py-2 pr-4 font-medium">항목</th>
                    <th className="py-2 pr-4 font-medium">Value</th>
                    <th className="py-2 font-medium">비고</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-line"><td className="py-2 pr-4">월간 비용</td><td className="py-2 pr-4">0원</td><td className="py-2">무료 한도</td></tr>
                  <tr className="border-b border-line"><td className="py-2 pr-4">Requests</td><td className="py-2 pr-4">1,024</td><td className="py-2">하루 평균</td></tr>
                </tbody>
              </table>
            </div>
          </Reply>
        </Section>

        <Section title="색">
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            {SWATCHES.map(([name, v]) => (
              <div key={name} className="flex flex-col gap-1">
                <div className="h-10 rounded-control border border-line" style={{ background: v }} />
                <span className="text-xs text-muted">{name}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="글자">
          <p className="text-2xl font-semibold">제목 2xl · Heading 123</p>
          <p className="text-base">본문 base · Body text 한글과 English</p>
          <p className="text-sm text-muted">보조 sm muted · Secondary 설명</p>
          <p className="text-xs text-muted">작은 글자 xs · Caption</p>
          <p style={{ fontFamily: "var(--haru-font-mono)" }}>코드 mono · const a = 1;</p>
        </Section>

        <Section title="버튼">
          <div className="flex flex-wrap gap-2">
            <Button variant="primary">기본 동작</Button>
            <Button>보조</Button>
            <Button variant="ghost">조용히</Button>
            <Button variant="danger">삭제</Button>
            <Button disabled>비활성</Button>
            <IconButton label="더 보기">⋯</IconButton>
            <IconButton label="선택됨" active>★</IconButton>
          </div>
        </Section>

        <Section title="입력창">
          <Input placeholder="한 줄 입력 (눌러서 포커스 확인)" />
          <Textarea placeholder="여러 줄 입력" />
        </Section>

        <Section title="탭 · 칩">
          <Tabs
            value={tab}
            onChange={setTab}
            options={[{ id: "chat", label: "Chat" }, { id: "work", label: "Work" }, { id: "code", label: "Code" }]}
            label="모드"
          />
          <div className="flex flex-wrap gap-2">
            {["all", "chat", "code"].map((c) => (
              <Chip key={c} selected={chip === c} onClick={() => setChip(c)}>
                {c === "all" ? "전체" : c === "chat" ? "채팅" : "Code"}
              </Chip>
            ))}
          </div>
        </Section>

        <Section title="칩 · 하위 메뉴 예시 (Code 입력창 아래 줄 모양)">
          <div className="relative flex flex-wrap gap-2">
            <Chip caret icon="☁">클라우드</Chip>
            <Chip caret icon="⎇">buriburiyj/haru</Chip>
            <Chip caret onClick={() => setChipMenu((v) => !v)}>{["자동", "GPT-6 Luna", "GPT-5.6 Terra", "GPT-5.6 Luna", "빠른 답변"][model]}</Chip>
            <Chip caret>Auto</Chip>
            {chipMenu && (
              <Menu className="absolute left-0 top-full z-10 mt-1 w-72">
                {["자동", "GPT-6 Luna", "GPT-5.6 Terra", "GPT-5.6 Luna", "빠른 답변"].map((m, i) => (
                  <MenuItem key={m} check={model === i} shortcut={String(i + 1)} hint={i === 0 ? "알아서 골라 줍니다" : undefined} onClick={() => setModel(i)}>
                    {m}
                  </MenuItem>
                ))}
                <MenuDivider />
                <SubMenu label="노력">
                  {["낮음", "보통", "높음", "최대"].map((e, i) => (
                    <MenuItem key={e} check={effort === i} hint={i === 3 ? "사용량이 많습니다" : undefined} onClick={() => setEffort(i)}>
                      {e}
                    </MenuItem>
                  ))}
                </SubMenu>
                <SubMenu label="더 많은 모델">
                  <MenuItem>Nemotron 3 Ultra</MenuItem>
                  <MenuItem>Mistral Large 4</MenuItem>
                </SubMenu>
                <MenuDivider />
                <MenuItem toggle={web} onClick={() => setWeb((v) => !v)}>웹 검색</MenuItem>
              </Menu>
            )}
          </div>
        </Section>

        <Section title="카드 · 메뉴 · 창">
          <Card>
            <p className="text-sm font-medium">카드 제목</p>
            <p className="mt-1 text-sm text-muted">카드 안의 설명 글입니다. 둥근 정도와 테두리를 확인하세요.</p>
          </Card>
          <div className="relative flex gap-2">
            <Button onClick={() => setMenu((v) => !v)}>메뉴 열기 ▾</Button>
            <Button onClick={() => setDialog(true)}>창 열기</Button>
            {menu && (
              <Menu className="absolute left-0 top-full z-10 mt-1">
                <MenuItem onClick={() => setMenu(false)}>이름 변경</MenuItem>
                <MenuItem onClick={() => setMenu(false)}>프로젝트로 이동</MenuItem>
                <MenuDivider />
                <MenuItem danger onClick={() => setMenu(false)}>삭제</MenuItem>
              </Menu>
            )}
          </div>
        </Section>
      </div>
      {dialog && (
        <Dialog
          title="예시 창"
          onClose={() => setDialog(false)}
          footer={
            <>
              <Button onClick={() => setDialog(false)}>취소</Button>
              <Button variant="primary" onClick={() => setDialog(false)}>확인</Button>
            </>
          }
        >
          <p className="text-sm">폰에서는 전체 화면, 큰 화면에서는 가운데 카드로 보입니다.</p>
        </Dialog>
      )}
    </div>
  );
}
