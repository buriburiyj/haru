import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { PermissionAnswer, PermissionMode, RunState, TaskEvent, TaskPermission, TaskSource, WorkFile, WorkRun } from "./types";

// useTask: the ONE place the progress screen gets its data from.
// Today the source is fakeSource (timed example data). To go live, pass a source built from the SSE function
// Codex adds to api.ts (the TaskSource interface in ./types is all it must satisfy). Screens never hold data themselves.

type State = { run: WorkRun; files: WorkFile[]; permission: TaskPermission | null };

const INITIAL: State = {
  run: { computer: "box", mode: "auto", state: "working", elapsed: 0, todos: [], actions: [] },
  files: [],
  permission: null,
};

function reduce(s: State, e: TaskEvent): State {
  switch (e.type) {
    case "reset":
      return INITIAL;
    case "meta":
      return { ...s, run: { ...s.run, ...(e.computer ? { computer: e.computer } : {}), ...(e.mode ? { mode: e.mode } : {}) } };
    case "state":
      return { ...s, run: { ...s.run, state: e.state } };
    case "todos":
      return { ...s, run: { ...s.run, todos: e.todos } };
    case "action": {
      const i = s.run.actions.findIndex((a) => a.id === e.action.id);
      const actions = i < 0 ? [...s.run.actions, e.action] : s.run.actions.map((a, k) => (k === i ? e.action : a));
      return { ...s, run: { ...s.run, actions } };
    }
    case "permission":
      return { ...s, permission: e.request };
    case "summary":
      return { ...s, run: { ...s.run, summary: e.summary } };
    case "files":
      return { ...s, files: e.files };
  }
}

export function useTask(source: TaskSource) {
  const [state, dispatch] = useReducer(reduce, INITIAL);
  const [elapsed, setElapsed] = useState(0);
  const conn = useRef<ReturnType<TaskSource["connect"]> | null>(null);
  const clock = useRef({ base: 0, at: Date.now() });
  const nextInterjection = useRef(0);

  useEffect(() => {
    dispatch({ type: "reset" });
    clock.current = { base: 0, at: Date.now() };
    setElapsed(0);
    const c = source.connect((e) => {
      if (e.type === "meta" && e.elapsed !== undefined) {
        clock.current = { base: e.elapsed, at: Date.now() };
        setElapsed(e.elapsed);
      }
      dispatch(e);
    });
    conn.current = c;
    return () => {
      c.close();
      conn.current = null;
    };
  }, [source]);

  // elapsed time ticks only while working
  const working = state.run.state === "working";
  useEffect(() => {
    if (!working) return;
    const t = setInterval(() => setElapsed(clock.current.base + Math.floor((Date.now() - clock.current.at) / 1000)), 1000);
    return () => clearInterval(t);
  }, [working]);

  const stop = useCallback(() => conn.current?.stop(), []);
  const interject = useCallback((text: string) => {
    const t = text.trim();
    if (!t) return;
    const id = `i-${nextInterjection.current++}`;
    // shown right away; the current step finishes first
    dispatch({ type: "action", action: { id, label: t, status: "pending", interjection: true } });
    conn.current?.interject(t, id);
  }, []);
  const decide = useCallback((answer: PermissionAnswer) => {
    const id = state.permission?.id;
    if (!id) return;
    dispatch({ type: "permission", request: null });
    conn.current?.answerPermission(id, answer);
  }, [state.permission?.id]);
  const rewind = useCallback((actionId: string) => conn.current?.rewind(actionId), []);
  const setMode = useCallback((mode: PermissionMode) => conn.current?.setMode(mode), []);

  const run: WorkRun = { ...state.run, elapsed };
  const runState: RunState = run.state;
  return { run, runState, files: state.files, permission: state.permission, stop, interject, decide, rewind, setMode };
}
