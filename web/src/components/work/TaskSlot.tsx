import { useEffect, useMemo, useState } from "react";
import { getTask, type TaskDetail } from "../../api";
import { attachSource, storedSource } from "../../work/sseSource";
import { useTask } from "../../work/useTask";
import ArtifactPanel from "../artifact/ArtifactPanel";
import type { ArtifactData } from "../artifact/types";
import PermissionCard from "../permission/PermissionCard";
import FileCard from "./FileCard";
import StatusChips from "./StatusChips";
import WorkProgress from "./WorkProgress";

/**
 * The place of a Work task inside a conversation (the empty assistant message with kind "task").
 * It loads the task from the server: a finished one is replayed from its stored events (nothing runs again),
 * one that still runs is followed live.
 */
export default function TaskSlot({ taskId }: { taskId: string }) {
  const [detail, setDetail] = useState<TaskDetail | null | "missing">(null);
  useEffect(() => {
    let alive = true;
    setDetail(null);
    getTask(taskId)
      .then((d) => alive && setDetail(d))
      .catch(() => alive && setDetail("missing"));
    return () => {
      alive = false;
    };
  }, [taskId]);

  if (detail === null) return <p className="text-sm text-muted">작업 기록을 불러오는 중…</p>;
  if (detail === "missing") {
    return <p className="text-sm text-muted">작업 기록을 찾을 수 없습니다. 서버가 다시 시작되면 지난 작업 기록은 사라집니다.</p>;
  }
  return <TaskSlotBody detail={detail} />;
}

function TaskSlotBody({ detail }: { detail: TaskDetail }) {
  const live = detail.status === "queued" || detail.status === "running";
  const source = useMemo(() => (live ? attachSource(detail) : storedSource(detail)), [detail, live]);
  const task = useTask(source);
  const [artifact, setArtifact] = useState<ArtifactData | null>(null);
  return (
    <div className="flex w-full flex-col gap-3">
      <WorkProgress run={task.run} onRewind={task.rewind} />
      {task.files.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">만든 파일</p>
          {task.files.map((f) => (
            <FileCard key={f.name} file={f} onOpen={setArtifact} />
          ))}
        </div>
      )}
      {live && <StatusChips computer={task.run.computer} mode={task.run.mode} elapsed={task.run.elapsed} state={task.run.state} />}
      {task.permission && (
        <PermissionCard
          request={{ title: task.permission.title, kind: task.permission.kind, detail: task.permission.detail }}
          onDecide={task.decide}
        />
      )}
      <ArtifactPanel artifact={artifact} onClose={() => setArtifact(null)} />
    </div>
  );
}
