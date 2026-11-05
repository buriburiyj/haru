import { useEffect, useMemo, useState } from "react";
import ArtifactPanel from "../artifact/ArtifactPanel";
import type { ArtifactData } from "../artifact/types";
import CopyToast from "../chat/CopyToast";
import Composer from "../Composer";
import PermissionCard from "../permission/PermissionCard";
import { Tabs, UserBubble } from "../ui";
import { fakeSource, type FakeScenario } from "../../work/fakeSource";
import { COMPUTER_LABEL, ISOLATED, type Computer } from "../../work/types";
import { useTask } from "../../work/useTask";
import FileCard from "./FileCard";
import PermissionModeMenu from "./PermissionModeMenu";
import StatusChips from "./StatusChips";
import WorkProgress from "./WorkProgress";

// Check screen for the work (진행) UI: open <site>/haru/?demo=work . No login, no server calls.
// The screen gets everything from useTask; the data comes from the fake source (see work/fakeSource.ts).

const SCENARIOS: { id: FakeScenario; label: string }[] = [
  { id: "working", label: "일하는 중" },
  { id: "ask", label: "허락 요청" },
  { id: "failed", label: "실패" },
  { id: "done", label: "끝남" },
];
const COMPUTERS: Computer[] = ["box", "tab", "actions", "codespaces"];

export default function WorkDemo() {
  const [scenario, setScenario] = useState<FakeScenario>("working");
  const [computer, setComputer] = useState<Computer>("box");
  const [text, setText] = useState("");
  const [web, setWeb] = useState(true);
  const [artifact, setArtifact] = useState<ArtifactData | null>(null);

  const source = useMemo(() => fakeSource(scenario, computer), [scenario, computer]);
  const task = useTask(source);
  const working = task.run.state === "working";

  // "전부 허용" only works on isolated computers
  useEffect(() => {
    if (!ISOLATED[task.run.computer] && task.run.mode === "all") task.setMode("auto");
  }, [task.run.computer, task.run.mode, task]);

  const submit = () => {
    const t = text.trim();
    if (!t) return;
    setText("");
    if (working) task.interject(t);
  };

  return (
    <div className="flex h-full bg-bg text-fg">
      <CopyToast />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-col gap-3 border-b border-line px-4 py-3">
          <h1 className="font-heading text-2xl font-light">진행 화면 확인</h1>
          <p className="text-xs text-muted">로그인 없이 보이는 확인용 화면입니다. 예시 데이터이고 서버와 통신하지 않습니다.</p>
          <div className="flex flex-wrap items-center gap-3">
            <Tabs value={scenario} options={SCENARIOS} onChange={setScenario} label="상황" />
            <Tabs value={computer} options={COMPUTERS.map((c) => ({ id: c, label: COMPUTER_LABEL[c] }))} onChange={setComputer} label="컴퓨터" />
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6">
            <UserBubble>jun-lab 저장소를 정리하고 README를 새로 써 줘. 끝나면 텔레그램으로 알려 줘.</UserBubble>
            <WorkProgress run={task.run} onRewind={task.rewind} />
            {task.files.length > 0 && (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-muted">만든 파일</p>
                {task.files.map((f) => (
                  <FileCard key={f.name} file={f} onOpen={setArtifact} />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="mx-auto flex w-full max-w-3xl flex-col gap-2 px-4 pb-2">
          <StatusChips computer={task.run.computer} mode={task.run.mode} elapsed={task.run.elapsed} state={task.run.state} />
          {task.permission && (
            <PermissionCard
              request={{ title: task.permission.title, kind: task.permission.kind, detail: task.permission.detail }}
              onDecide={task.decide}
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
            onStop={task.stop}
          />
          <div className="flex flex-wrap items-center gap-2">
            <PermissionModeMenu mode={task.run.mode} onChange={task.setMode} isolated={ISOLATED[task.run.computer]} />
          </div>
        </div>
      </div>
      <ArtifactPanel artifact={artifact} onClose={() => setArtifact(null)} />
    </div>
  );
}
