import { useCallback, useEffect, useState } from "react";
import { getUsage, type ProviderUsage, type UsageInfo } from "../../api";
import { Button, Card } from "../ui";

const fmtTime = (sec: number) =>
  new Date(sec * 1000).toLocaleString("ko-KR", { year: "numeric", month: "long", day: "numeric", hour: "numeric", minute: "2-digit" });

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-fg-2">{label}</span>
      <span className="text-fg">{value}</span>
    </div>
  );
}

function CodexCard({ codex }: { codex: UsageInfo["codex"] }) {
  if (!codex)
    return (
      <Card className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-fg">Codex</h3>
        <p className="text-sm text-muted">GitHub에 연결하지 못해 Codex 사용량을 가져오지 못했습니다</p>
      </Card>
    );
  const pct = codex.minutes_limit > 0 ? Math.min(100, Math.round((codex.minutes_used / codex.minutes_limit) * 100)) : 0;
  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-fg">Codex</h3>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-sm">
          <span className="text-fg-2">이번 달 사용</span>
          <span className="text-fg">
            {codex.minutes_used}분 / {codex.minutes_limit}분
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          aria-label="Codex 사용 분"
          className="h-1.5 w-full overflow-hidden rounded-pill bg-surface-2"
        >
          <div className="h-full rounded-pill bg-accent" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <Stat label="실행 횟수" value={`${codex.runs}회`} />
      <Stat label="초기화" value={fmtTime(codex.resets_at)} />
    </Card>
  );
}

function ProviderCard({ name, u }: { name: string; u: ProviderUsage }) {
  return (
    <Card className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-fg">{name}</h3>
      <Stat label="오늘 호출 수" value={`${u.calls_today}회`} />
      <Stat label="한도 초과(429) 횟수" value={`${u.rate_limited_today}회`} />
      <Stat label="초기화 시각" value={fmtTime(u.resets_at)} />
    </Card>
  );
}

/** Usage page: GET /usage. Read-only numbers, no billing. */
export default function UsagePanel() {
  const [data, setData] = useState<UsageInfo | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    setData(null);
    setErr("");
    getUsage().then(setData, (e) =>
      setErr(e instanceof Error && e.message === "unauthorized" ? "다시 로그인해 주세요" : "사용량을 불러오지 못했습니다"),
    );
  }, []);
  useEffect(load, [load]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className="mr-auto text-xs text-muted">{data ? `${fmtTime(data.as_of)} 기준` : ""}</span>
        <Button onClick={load}>새로고침</Button>
      </div>
      {err ? (
        <p className="text-sm text-danger">{err}</p>
      ) : !data ? (
        <p className="text-sm text-muted">불러오는 중…</p>
      ) : (
        <>
          <CodexCard codex={data.codex} />
          <ProviderCard name="Groq" u={data.groq} />
          <ProviderCard name="NVIDIA" u={data.nvidia} />
        </>
      )}
    </div>
  );
}
