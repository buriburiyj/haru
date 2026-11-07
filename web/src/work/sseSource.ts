import { createTask, decideTaskPermission, messageTask, rewindTask, setTaskMode, stopTask, taskEvents, type ActiveTask, type PermissionMode as ServerMode } from "../api";
import type { Computer, PermissionAnswer, PermissionMode, TaskConnection, TaskEvent, TaskPermission, TaskSource, WorkAction, WorkSummary } from "./types";

// Real TaskSource: POST /tasks, then GET /tasks/{id}/events (SSE). It turns the server's events (server/API.md,
// "Background tasks and worker") into the TaskEvent the screens understand. Screens and useTask do not change.
// Events are matched by id (action.id = output.id = skipped.id = error.id), never by command text.

const TO_SERVER: Record<PermissionMode, ServerMode> = {
  ask: "always_ask",
  "auto-edit": "auto_edit",
  plan: "plan",
  auto: "auto",
  quiet: "skip",
  all: "allow_all",
};
const FROM_SERVER: Record<string, PermissionMode> = {
  always_ask: "ask",
  auto_edit: "auto-edit",
  plan: "plan",
  auto: "auto",
  skip: "quiet",
  allow_all: "all",
};
const COMPUTER: Record<string, Computer> = { mac: "box", box: "box", tab: "tab", actions: "actions", codespaces: "codespaces" };
const CHANGE: Record<string, "추가" | "수정" | "삭제"> = { added: "추가", modified: "수정", deleted: "삭제" };
const TERMINAL = new Set(["done", "failed", "stopped"]);

type Json = Record<string, unknown>;
const str = (v: unknown, fallback = "") => (v === undefined || v === null ? fallback : String(v));

/** Stateful translator: one server event in, zero or more TaskEvents out. */
function makeMapper(emit: (e: TaskEvent) => void, opts: { statusElapsed: boolean } = { statusElapsed: true }) {
  let n = 0;
  const actions = new Map<string, WorkAction>();
  const skipped: { text: string; reason: string }[] = [];
  let summarySent = false;
  // interjections: the screen already shows a row with a local id; the server confirms with its own id
  const interjections: { localId: string; text: string; serverId?: string }[] = [];

  const upsert = (a: WorkAction) => {
    actions.set(a.id, a);
    emit({ type: "action", action: a });
    return a;
  };
  const patch = (id: string, change: Partial<WorkAction>, fallbackLabel: string) => {
    const old = actions.get(id);
    return upsert(old ? { ...old, ...change } : { id, label: fallbackLabel, status: "running", ...change });
  };
  const finishRunning = (status: "done" | "skipped" = "done", reason?: string) => {
    for (const a of actions.values()) if (a.status === "running") upsert({ ...a, status, ...(reason ? { reason } : {}) });
  };

  function handle(event: string, d: Json) {
    switch (event) {
      case "task": {
        const mode = FROM_SERVER[str(d.mode)];
        emit({ type: "meta", ...(mode ? { mode } : {}), elapsed: 0 });
        emit({ type: "state", state: "working" });
        break;
      }
      case "todos": {
        const list = Array.isArray(d.todos) ? d.todos : [];
        emit({ type: "todos", todos: list.map((t) => ({ id: str((t as Json).id), text: str((t as Json).text), done: !!(t as Json).done })) });
        break;
      }
      case "status": {
        const computer = COMPUTER[str(d.computer ?? d.worker).toLowerCase()];
        const elapsed = opts.statusElapsed && typeof d.elapsed === "number" ? d.elapsed : undefined;
        emit({ type: "meta", ...(computer ? { computer } : {}), ...(elapsed !== undefined ? { elapsed } : {}) });
        const s = str(d.status);
        if (s === "failed") emit({ type: "state", state: "failed" });
        else if (s === "stopped") emit({ type: "state", state: "stopped" });
        else emit({ type: "state", state: "working" }); // queued / running (done comes with the `done` event)
        break;
      }
      case "action": {
        const id = str(d.id, `a${++n}`);
        const status = (["running", "pending", "done", "failed", "skipped"] as const).find((s) => s === str(d.status)) ?? "running";
        patch(id, { label: str(d.label) || str(d.command, "작업"), status, outward: d.outward === true }, str(d.label) || str(d.command));
        break;
      }
      case "checkpoint": {
        const id = str(d.action_id);
        if (id && actions.has(id)) patch(id, { checkpoint: true }, "");
        break;
      }
      case "output": {
        const id = str(d.id);
        const text = str(d.text);
        const detail = { kind: d.is_diff === true ? ("diff" as const) : ("output" as const), text };
        const old = actions.get(id);
        patch(id, { detail, status: old && (old.status === "failed" || old.status === "skipped") ? old.status : "done" }, str(d.command, "출력"));
        break;
      }
      case "permission_required": {
        const kind = str(d.kind);
        const permission: TaskPermission = {
          id: str(d.id ?? d.action_id, "p1"),
          title: str(d.title, "이 행동을 해도 될까요?"),
          kind: kind === "delete" || kind === "send" || kind === "pay" ? kind : "normal",
          ...(d.command ? { detail: str(d.command) } : {}),
        };
        emit({ type: "permission", request: permission });
        break;
      }
      case "permission": {
        emit({ type: "permission", request: null }); // the decision was recorded
        break;
      }
      case "interjection": {
        const sid = str(d.id);
        const text = str(d.content);
        const mine = interjections.find((i) => !i.serverId && i.text === text);
        if (mine) mine.serverId = sid;
        upsert({ id: mine?.localId ?? `ix-${sid}`, label: text, status: "pending", interjection: true });
        break;
      }
      case "interjection_applied": {
        const sid = str(d.id);
        const mine = interjections.find((i) => i.serverId === sid);
        const id = mine?.localId ?? `ix-${sid}`;
        const old = actions.get(id);
        upsert({ ...(old ?? { id, label: "끼어들기", interjection: true }), status: "done" });
        break;
      }
      case "skipped": {
        const id = str(d.id);
        const reason = str(d.reason);
        const old = actions.get(id);
        const text = old?.label || str(d.command, reason);
        patch(id || `a${++n}`, { status: "skipped", reason }, text);
        skipped.push({ text, reason });
        emit({ type: "permission", request: null });
        break;
      }
      case "error": {
        const code = d.exit_code !== undefined && d.exit_code !== null ? ` (종료 코드 ${str(d.exit_code)})` : "";
        const detail = d.output ? { kind: "output" as const, text: str(d.output) } : undefined;
        patch(str(d.id) || `a${++n}`, { status: "failed", reason: `${str(d.reason, "실패했습니다")}${code}`, ...(detail ? { detail } : {}) }, str(d.command, "작업"));
        break;
      }
      case "summary": {
        const files = Array.isArray(d.files) ? d.files : [];
        const fromServer = Array.isArray(d.skipped) ? d.skipped : [];
        const summary: WorkSummary = {
          did: d.text ? [str(d.text)] : [],
          files: files.map((f) => {
            const o = (typeof f === "string" ? { path: f } : f) as Json;
            return { name: str(o.path ?? o.name), change: CHANGE[str(o.change)] ?? "수정" };
          }),
          skipped: [
            ...fromServer.map((s) => {
              const o = (typeof s === "string" ? { text: s } : s) as Json;
              return { text: str(o.text ?? o.command ?? o.label), reason: str(o.reason) };
            }),
            ...skipped.filter((s) => !fromServer.some((x) => str((x as Json).command ?? (x as Json).text) === s.text)),
          ],
          usage: (Array.isArray(d.usage) ? d.usage : []).map((u) => ({ label: str((u as Json).label), value: str((u as Json).value) })),
        };
        summarySent = true;
        emit({ type: "summary", summary });
        break;
      }
      case "done": {
        finishRunning("done");
        emit({ type: "state", state: "done" });
        const result = str(d.result);
        if (!summarySent && result) emit({ type: "summary", summary: { did: [result], files: [], skipped, usage: [] } });
        break;
      }
      case "failed": {
        finishRunning("skipped", "중단되었습니다.");
        const error = str(d.error, "작업이 실패했습니다.");
        if (![...actions.values()].some((a) => a.status === "failed")) upsert({ id: `a${++n}`, label: "작업이 실패했습니다", status: "failed", reason: error });
        emit({ type: "state", state: "failed" });
        break;
      }
      case "mode_changed": {
        const mode = FROM_SERVER[str(d.mode)];
        if (mode) emit({ type: "meta", mode });
        break;
      }
      case "rewind_requested": {
        patch(`rewind-${str(d.id)}`, { label: "체크포인트로 되돌리는 중", status: "running" }, "체크포인트로 되돌리는 중");
        break;
      }
      case "rewound": {
        patch(`rewind-${str(d.id)}`, { label: "체크포인트로 되돌렸습니다", status: "done" }, "체크포인트로 되돌렸습니다");
        break;
      }
      case "stopped": {
        finishRunning("skipped", "멈췄습니다.");
        emit({ type: "state", state: "stopped" });
        break;
      }
    }
  }

  return {
    handle,
    addInterjection(localId: string, text: string) {
      interjections.push({ localId, text });
    },
    /** Local failure (could not create the task, stream lost for good): shown as a failed row. */
    failed(label: string, reason: string, state: "failed" | "working" = "failed") {
      if (state === "failed") finishRunning("skipped", "중단되었습니다.");
      upsert({ id: `local-${++n}`, label, status: "failed", reason });
      emit({ type: "state", state });
    },
  };
}

/** Reads an SSE response and calls onEvent(event, data, id) for every complete block. */
async function readSse(res: Response, onEvent: (event: string, data: Json, id: number | null) => void): Promise<void> {
  if (!res.body) return;
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.search(/\r?\n\r?\n/)) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i).replace(/^\r?\n\r?\n/, "");
      const ev = /^event: ?(.*)$/m.exec(block)?.[1]?.trim();
      const idText = /^id: ?(\d+)$/m.exec(block)?.[1];
      const data = [...block.matchAll(/^data: ?(.*)$/gm)].map((m) => m[1]).join("\n");
      if (!ev || !data) continue; // comments / keep-alive
      try {
        const parsed = JSON.parse(data);
        onEvent(ev, parsed && typeof parsed === "object" ? (parsed as Json) : { value: parsed }, idText ? Number(idText) : null);
      } catch {
        /* a broken block is skipped */
      }
    }
  }
}

function explain(err: unknown): string {
  const status = (err as { status?: number })?.status;
  if ((err as Error)?.message === "unauthorized" || status === 401) return "다시 로그인해 주세요.";
  if (status === 409) return "작업이 이미 끝났거나 지금은 할 수 없는 상태입니다.";
  if (status === 502 || status === 503) return "서버가 지금 작업을 받을 수 없습니다. 잠시 뒤에 다시 시도해 주세요.";
  if (status) return `서버가 요청을 받지 못했습니다 (오류 ${status}).`;
  return "서버에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.";
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export type SseSourceOptions = { prompt: string; mode: PermissionMode; conversationId?: string };

/**
 * Follows one task on the server. `taskId` resolves to the id (or null when it could not be created).
 * Reconnects up to 5 times with taskEvents(id, after). Mode change and rewind go to the real endpoints.
 */
function connectTask(emit: (e: TaskEvent) => void, taskId: Promise<string | null>, map: ReturnType<typeof makeMapper>): TaskConnection {
  const ctrl = new AbortController();

  async function follow(id: string) {
    let after = 0;
    let tries = 0;
    let finished = false;
    while (!ctrl.signal.aborted && !finished) {
      try {
        const res = after > 0 ? await taskEvents(id, after, ctrl.signal) : await taskEvents(id, ctrl.signal);
        tries = 0;
        await readSse(res, (event, data, sid) => {
          if (sid !== null) after = sid;
          if (TERMINAL.has(event)) finished = true;
          map.handle(event, data);
        });
        if (!finished) throw new Error("stream ended");
      } catch (err) {
        if (ctrl.signal.aborted) return;
        const status = (err as { status?: number })?.status;
        if (status === 401 || status === 403 || status === 404 || ++tries > 5) {
          map.failed("서버와 연결이 끊겼습니다", `${explain(err)} 작업은 서버에서 계속될 수 있습니다.`, "working");
          return;
        }
        await sleep(Math.min(8000, 1000 * 2 ** (tries - 1)));
      }
    }
  }
  void taskId.then((id) => (id ? follow(id) : undefined));

  return {
    stop() {
      // the server answers with a `stopped` event; nothing is faked locally
      void taskId.then(async (id) => {
        if (id) await stopTask(id).catch(() => map.failed("멈추지 못했습니다", "서버에 연결할 수 없습니다.", "working"));
      });
    },
    interject(text, id) {
      map.addInterjection(id, text);
      void taskId.then(async (tid) => {
        if (tid) await messageTask(tid, text).catch(() => map.failed("끼어들기를 보내지 못했습니다", "작업이 끝났거나 서버에 연결할 수 없습니다.", "working"));
      });
    },
    answerPermission(_requestId: string, answer: PermissionAnswer) {
      void taskId.then(async (tid) => {
        if (tid) await decideTaskPermission(tid, answer === "once" ? "allow" : answer).catch(() => map.failed("허락을 전하지 못했습니다", "서버에 연결할 수 없습니다.", "working"));
      });
    },
    rewind(actionId) {
      void taskId.then(async (tid) => {
        if (!tid) return;
        try {
          const r = await rewindTask(tid, actionId);
          if (!r.ok) map.failed("되돌리지 못했습니다", r.reason ?? "되돌릴 수 없는 행동입니다.", "working");
          // on success the server sends rewind_requested, then rewound
        } catch (err) {
          map.failed("되돌리지 못했습니다", explain(err), "working");
        }
      });
    },
    setMode(mode) {
      // the chip changes when the server answers with `mode_changed`
      void taskId.then(async (tid) => {
        if (!tid) return;
        try {
          await setTaskMode(tid, TO_SERVER[mode]);
        } catch (err) {
          map.failed("허락 모드를 바꾸지 못했습니다", (err as { detail?: string })?.detail || explain(err), "working");
        }
      });
    },
    close() {
      ctrl.abort();
    },
  };
}

/** Real source for Work mode: starts the task on the server and follows its events. */
export function sseSource(opts: SseSourceOptions): TaskSource {
  return {
    connect(emit): TaskConnection {
      const map = makeMapper(emit);
      emit({ type: "meta", mode: opts.mode, elapsed: 0 });
      emit({ type: "state", state: "working" });
      const taskId: Promise<string | null> = createTask(opts.prompt, TO_SERVER[opts.mode], opts.conversationId ?? "")
        .then((t) => t.id)
        .catch((err) => {
          map.failed("작업을 시작하지 못했습니다", explain(err));
          return null;
        });
      return connectTask(emit, taskId, map);
    },
  };
}

/**
 * Source for a task that is already running on the server (after a page refresh): GET /tasks?active=true gave `task`.
 * The whole event list is replayed, but the clock comes from `task.elapsed`, not from the replayed status events.
 */
export function attachSource(task: ActiveTask): TaskSource {
  return {
    connect(emit): TaskConnection {
      const map = makeMapper(emit, { statusElapsed: false });
      const computer = COMPUTER[str(task.computer).toLowerCase()];
      emit({ type: "meta", mode: FROM_SERVER[task.mode], ...(computer ? { computer } : {}), elapsed: task.elapsed });
      emit({ type: "state", state: "working" });
      return connectTask(emit, Promise.resolve(task.id), map);
    },
  };
}
