import { useEffect, useMemo, useState } from "react";
import ArtifactPanel from "../artifact/ArtifactPanel";
import type { ArtifactData } from "../artifact/types";
import CopyToast from "../chat/CopyToast";
import Composer from "../Composer";
import PermissionCard from "../permission/PermissionCard";
import { Tabs, UserBubble } from "../ui";
import FileCard from "./FileCard";
import PermissionModeMenu from "./PermissionModeMenu";
import { SAMPLE_FILES, SAMPLE_RUN_DONE, SAMPLE_RUN_WORKING } from "./sample";
import StatusChips from "./StatusChips";
import { COMPUTER_LABEL, ISOLATED, type Computer, type PermissionMode, type WorkAction, type WorkRun } from "./types";
import WorkProgress from "./WorkProgress";

// Check screen for the work (진행) UI: open <site>/haru/?demo=work . No login, no server calls. Example data only.

type Scenario = "working" | "done" | "failed" | "ask";
const SCENARIOS: { id: Scenario; label: string }[] = [
  { id: "working", label: "일하는 중" },
  { id: "ask", label: "허락 요청" },
  { id: "failed", label: "실패" },
  { id: "done", label: "끝남" },
];
const COMPUTERS: Computer[] = ["box", "tab", "actions", "codespaces"];

export default function WorkDemo() {
  const [scenario, setScenario] = useState<Scenario>("working");
  const [computer, setComputer] = useState<Computer>("box");
  const [mode, setMode] = useState<PermissionMode>("auto");
  const [stopped, setStopped] = useState(false);
  const [elapsed, setElapsed] = useState(SAMPLE_RUN_WORKING.elapsed);
  const [extra, setExtra] = useState<WorkAction[]>([]);
  const [text, setText] = useState("");
  const [web, setWeb] = useState(true);
  const [artifact, setArtifact] = useState<ArtifactData | null>(null);
  const [permOpen, setPermOpen] = useState(true);

  const working = (scenario === "working" || scenario === "ask") && !stopped;

  // elapsed time ticks only while working
  useEffect(() => {
    if (!working) return;
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, [working]);

  const pickScenario = (s: Scenario) => {
    setScenario(s);
    setStopped(false);
    setExtra([]);
    setPermOpen(true);
    setElapsed(s === "done" ? SAMPLE_RUN_DONE.elapsed : SAMPLE_RUN_WORKING.elapsed);
  };

  const pickComputer = (c: Computer) => {
    setComputer(c);
    if (!ISOLATED[c] && mode === "all") setMode("auto"); // 전부 허용 only on isolated computers
  };

  const run: WorkRun = useMemo(() => {
    const base = scenario === "done" ? SAMPLE_RUN_DONE : SAMPLE_RUN_WORKING;
    let actions = [...base.actions, ...extra];
    let state: WorkRun["state"] = scenario === "done" ? "done" : "working";
    if (scenario === "failed") {
      state = "failed";
      actions = actions.map((a) => (a.status === "running" ? { ...a, status: "failed", reason: "다시 실행한 테스트도 실패했습니다. 3번 시도해 보고 멈춥니다." } : a));
    }
    if (stopped) {
      state = "stopped";
      actions = actions.map((a) => (a.status === "running" ? { ...a, status: "skipped", reason: "멈췄습니다." } : a));
    }
    return { ...base, computer, mode, state, elapsed, actions };
  }, [scenario, stopped, extra, computer, mode, elapsed]);

  const submit = () => {
    const t = text.trim();
    if (!t) return;
    setText("");
    if (working) setExtra((x) => [...x, { id: `i${x.length}`, label: t, status: "pending", interjection: true }]);
  };

  return (
    <div className="flex h-full bg-bg text-fg">
      <CopyToast />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-col gap-3 border-b border-line px-4 py-3">
          <h1 className="font-heading text-2xl font-light">진행 화면 확인</h1>
          <p className="text-xs text-muted">로그인 없이 보이는 확인용 화면입니다. 예시 데이터이고 서버와 통신하지 않습니다.</p>
          <div className="flex flex-wrap items-center gap-3">
            <Tabs value={scenario} options={SCENARIOS} onChange={pickScenario} label="상황" />
            <Tabs value={computer} options={COMPUTERS.map((c) => ({ id: c, label: COMPUTER_LABEL[c] }))} onChange={pickComputer} label="컴퓨터" />
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6">
            <UserBubble>jun-lab 저장소를 정리하고 README를 새로 써 줘. 끝나면 텔레그램으로 알려 줘.</UserBubble>
            <WorkProgress run={run} onRewind={() => {}} />
            {scenario === "done" && (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-muted">만든 파일</p>
                {SAMPLE_FILES.map((f) => (
                  <FileCard key={f.name} file={f} onOpen={setArtifact} />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="mx-auto flex w-full max-w-3xl flex-col gap-2 px-4 pb-2">
          <StatusChips computer={computer} mode={mode} elapsed={elapsed} state={run.state} />
          {scenario === "ask" && !stopped && permOpen && (
            <PermissionCard
              request={{ title: "GitHub: jun-lab에 파일 3개 올리기", kind: "normal", detail: "파일 3개: README.md, docs/usage.md, scripts/run.py" }}
              onDecide={() => setPermOpen(false)}
            />
          )}
          <Composer
            value={text}
            onChange={setText}
            onSubmit={submit}
            busy={false}
            model="auto"
            effort="medium"
            onModelChange={() => {}}
            mode="chat"
            onModeChange={() => {}}
            hideModeSwitch
            models={[{ id: "auto", label: "자동", provider: "auto" }]}
            attachments={[]}
            onAttach={() => {}}
            onRemoveAttachment={() => {}}
            web={web}
            onWebChange={setWeb}
            working={working}
            onStop={() => setStopped(true)}
          />
          <div className="flex flex-wrap items-center gap-2">
            <PermissionModeMenu mode={mode} onChange={setMode} isolated={ISOLATED[computer]} />
          </div>
        </div>
      </div>
      <ArtifactPanel artifact={artifact} onClose={() => setArtifact(null)} />
    </div>
  );
}
