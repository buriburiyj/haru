import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { INITIAL_TASK_STATE, reduceTask } from "./useTask";
import type { PermissionAnswer, PermissionMode, TaskConnection, TaskEvent, TaskPermission, TaskSource, WorkFile, WorkRun } from "./types";

// useTaskThread: all work tasks of one conversation (each message sent in Work mode starts one task).
// Same data path as useTask: a TaskSource pushes events, the screen only reads state. Swap the source later, nothing else changes.

export type TaskItem = { id: string; prompt: string; run: WorkRun; files: WorkFile[]; permission: TaskPermission | null };
type Raw = { id: string; prompt: string } & typeof INITIAL_TASK_STATE;
type Action = { type: "add"; id: string; prompt: string } | { type: "event"; id: string; event: TaskEvent } | { type: "clear" };

function threadReduce(items: Raw[], a: Action): Raw[] {
  if (a.type === "clear") return [];
  if (a.type === "add") return [...items, { id: a.id, prompt: a.prompt, ...INITIAL_TASK_STATE }];
  return items.map((t) => (t.id === a.id ? { ...t, ...reduceTask(t, a.event) } : t));
}

type Clock = { base: number; at: number; frozen: boolean };

export function useTaskThread(makeSource: (opts: { prompt: string; mode: PermissionMode }) => TaskSource) {
  const [raw, dispatch] = useReducer(threadReduce, []);
  const [, tick] = useState(0);
  const conns = useRef(new Map<string, TaskConnection>());
  const clocks = useRef(new Map<string, Clock>());
  const counter = useRef(0);
  const interjections = useRef(0);

  const elapsedOf = (id: string): number => {
    const c = clocks.current.get(id);
    if (!c) return 0;
    return c.frozen ? c.base : c.base + Math.floor((Date.now() - c.at) / 1000);
  };

  const anyWorking = raw.some((t) => t.run.state === "working");
  useEffect(() => {
    if (!anyWorking) return;
    const t = setInterval(() => tick((n) => n + 1), 1000); // re-render so the elapsed time moves
    return () => clearInterval(t);
  }, [anyWorking]);

  // close every connection on unmount
  useEffect(() => {
    const map = conns.current;
    return () => map.forEach((c) => c.close());
  }, []);

  const start = useCallback(
    (prompt: string, mode: PermissionMode) => {
      const id = `task-${++counter.current}`;
      dispatch({ type: "add", id, prompt });
      clocks.current.set(id, { base: 0, at: Date.now(), frozen: false });
      const c = makeSource({ prompt, mode }).connect((e) => {
        if (e.type === "meta" && e.elapsed !== undefined) clocks.current.set(id, { base: e.elapsed, at: Date.now(), frozen: false });
        if (e.type === "state" && e.state !== "working") clocks.current.set(id, { base: elapsedOf(id), at: Date.now(), frozen: true });
        dispatch({ type: "event", id, event: e });
      });
      conns.current.set(id, c);
      return id;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [makeSource],
  );

  const tasks: TaskItem[] = raw.map((t) => ({ id: t.id, prompt: t.prompt, run: { ...t.run, elapsed: elapsedOf(t.id) }, files: t.files, permission: t.permission }));
  const active = tasks[tasks.length - 1] as TaskItem | undefined;
  const activeId = active?.id;

  const stop = useCallback(() => activeId && conns.current.get(activeId)?.stop(), [activeId]);
  const interject = useCallback(
    (text: string) => {
      const t = text.trim();
      if (!t || !activeId) return;
      const id = `i-${++interjections.current}`;
      dispatch({ type: "event", id: activeId, event: { type: "action", action: { id, label: t, status: "pending", interjection: true } } });
      conns.current.get(activeId)?.interject(t, id);
    },
    [activeId],
  );
  const decide = useCallback(
    (answer: PermissionAnswer) => {
      const req = active?.permission;
      if (!activeId || !req) return;
      dispatch({ type: "event", id: activeId, event: { type: "permission", request: null } });
      conns.current.get(activeId)?.answerPermission(req.id, answer);
    },
    [activeId, active?.permission],
  );
  const rewind = useCallback((taskId: string, actionId: string) => conns.current.get(taskId)?.rewind(actionId), []);
  const setMode = useCallback((mode: PermissionMode) => activeId && conns.current.get(activeId)?.setMode(mode), [activeId]);

  return { tasks, active, working: active?.run.state === "working", start, stop, interject, decide, rewind, setMode };
}
