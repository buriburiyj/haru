import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import ArtifactPanel from "../artifact/ArtifactPanel";
import type { ArtifactData } from "../artifact/types";
import CopyToast from "../chat/CopyToast";
import TopBar from "../chat/TopBar";
import PermissionCard from "../permission/PermissionCard";
import { TempChatBanner } from "../temp/TempChat";
import { UserBubble } from "../ui";
import type { TaskItem } from "../../work/useTaskThread";
import type { PermissionAnswer } from "../../work/types";
import FileCard from "./FileCard";
import StatusChips from "./StatusChips";
import WorkProgress from "./WorkProgress";

/**
 * A conversation in Work mode: each message sent starts a task, shown as the user's message plus its progress.
 * Pure view: data and actions come in through props (from useTaskThread).
 */
export default function WorkChatView({
  tasks,
  composer,
  onRewind,
  onDecide,
  onMenu,
}: {
  tasks: TaskItem[];
  /** the composer area (input + permission mode chip), pinned to the bottom */
  composer: ReactNode;
  onRewind: (taskId: string, actionId: string) => void;
  onDecide: (answer: PermissionAnswer) => void;
  onMenu: () => void;
}) {
  const [artifact, setArtifact] = useState<ArtifactData | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const active = tasks[tasks.length - 1];
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [tasks.length, active?.run.actions.length, active?.run.state]);

  return (
    <div className="flex h-full bg-bg text-fg">
      <CopyToast />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar title={tasks[0]?.prompt.slice(0, 40) || "Work"} onMenu={onMenu} />
        <TempChatBanner />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6">
            {tasks.map((t) => (
              <section key={t.id} className="flex flex-col gap-4">
                <UserBubble>{t.prompt}</UserBubble>
                <WorkProgress run={t.run} onRewind={(a) => onRewind(t.id, a)} />
                {t.files.length > 0 && (
                  <div className="flex flex-col gap-3">
                    <p className="text-sm text-muted">만든 파일</p>
                    {t.files.map((f) => (
                      <FileCard key={f.name} file={f} onOpen={setArtifact} />
                    ))}
                  </div>
                )}
              </section>
            ))}
            <div ref={endRef} />
          </div>
        </div>
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-2 px-4 pb-2">
          {active && <StatusChips computer={active.run.computer} mode={active.run.mode} elapsed={active.run.elapsed} state={active.run.state} />}
          {active?.permission && (
            <PermissionCard
              request={{ title: active.permission.title, kind: active.permission.kind, detail: active.permission.detail }}
              onDecide={onDecide}
            />
          )}
          {composer}
        </div>
      </div>
      <ArtifactPanel artifact={artifact} onClose={() => setArtifact(null)} />
    </div>
  );
}
