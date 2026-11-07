import { createTask, decideTaskPermission, messageTask, stopTask, taskEvents, type PermissionMode as ServerMode } from "../api";
import type { Computer, PermissionAnswer, PermissionMode, TaskConnection, TaskEvent, TaskPermission, TaskSource, WorkAction, WorkSummary } from "./types";

// Real TaskSource: POST /tasks, then GET /tasks/{id}/events (SSE). It turns the server's events (server/API.md,
// "Background tasks and worker") into the TaskEvent the screens understand. Screens and useTask do not change.
// Gaps between the server contract and work/types.ts are listed in the report of this change (not patched here).

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

/** The server sends `worker` as free text; pick the computer we can recognise, otherwise leave it as it was. */
function computerOf(worker: unknown): Computer | undefined {
  const w = String(worker ?? "").toLowerCase();
  if (/codespace/.test(w)) return "codespaces";
  if (/action/.test(w)) return "actions";
  if (/tab|termux|s6/.test(w)) return "tab";
  if (/box|mac|lima|local/.test(w)) return "box";
  return undefined;
}

/**
 * The server does not say what kind of action needs permission, so classify the command here as a safety net:
 * delete / send / pay never get [항상 허락]. (Codex should send `kind` itself; see the report.)
 */
export function permissionKindOf(command: string): TaskPermission["kind"] {
  if (/\b(rm|rmdir|unlink|shred|truncate)\b|\bgit\s+(clean|reset\s+--hard)\b|\bdrop\s+(table|database)\b|\bdelete\b/i.test(command)) return "delete";
  if (/\bgit\s+push\b|\b(scp|rsync|sendmail|mail|mutt|ssh)\b|\bcurl\b[^|;]*(-X\s*(POST|PUT|PATCH|DELETE)|--data|-d\s|-F\s)|\bgh\s+(pr|issue|release)\s+(create|comment|merge)|\bnpm\s+publish\b|\bdeploy\b/i.test(command)) return "send";
  if (/\b(pay|payment|purchase|checkout|billing|stripe)\b/i.test(command)) return "pay";
  return "normal";
}

const looksLikeDiff = (t: string) => /^diff --git|^@@ |^\+\+\+ /m.test(t);

type Json = Record<string, unknown>;

/** Stateful translator: one server event in, zero or more TaskEvents out. */
function makeMapper(emit: (e: TaskEvent) => void) {
  let n = 0;
  let nPerm = 0;
  const actions: WorkAction[] = [];
  let runningId: string | null = null;
  const skipped: { text: string; reason: string }[] = [];
  let summarySent = false;

  const upsert = (a: WorkAction) => {
    const i = actions.findIndex((x) => x.id === a.id);
    if (i < 0) actions.push(a);
    else actions[i] = a;
    emit({ type: "action", action: a });
    return a;
  };
  const byCommand = (cmd: unknown) => [...actions].reverse().find((a) => a.label === String(cmd ?? ""));
  const finishRunning = (status: "done" | "skipped" = "done", reason?: string) => {
    const a = actions.find((x) => x.id === runningId);
    if (a && a.status === "running") upsert({ ...a, status, ...(reason ? { reason } : {}) });
    runningId = null;
  };

  function handle(event: string, d: Json) {
    switch (event) {
      case "task": {
        const mode = FROM_SERVER[String(d.mode)];
        emit({ type: "meta", ...(mode ? { mode } : {}), elapsed: 0 });
        emit({ type: "state", state: "working" });
        break;
      }
      case "status": {
        const computer = computerOf(d.worker);
        if (computer) emit({ type: "meta", computer });
        const s = String(d.status ?? "");
        if (s === "failed") emit({ type: "state", state: "failed" });
        else if (s === "stopped") emit({ type: "state", state: "stopped" });
        else emit({ type: "state", state: "working" }); // queued / running (done comes with the `done` event)
        break;
      }
      case "action": {
        finishRunning();
        const a = upsert({ id: `a${++n}`, label: String(d.command ?? ""), status: "running" });
        runningId = a.id;
        break;
      }
      case "output": {
        const a = byCommand(d.command) ?? actions.find((x) => x.id === runningId);
        const text = String(d.text ?? "");
        const detail = { kind: looksLikeDiff(text) ? ("diff" as const) : ("output" as const), text };
        if (a) {
          upsert({ ...a, detail, status: a.status === "failed" || a.status === "skipped" ? a.status : "done" });
          if (a.id === runningId) runningId = null;
        } else upsert({ id: `a${++n}`, label: String(d.command ?? "출력"), status: "done", detail });
        break;
      }
      case "checkpoint": {
        const a = byCommand(d.command);
        if (a) upsert({ ...a, checkpoint: true });
        break;
      }
      case "permission_required": {
        emit({
          type: "permission",
          request: { id: `p${++nPerm}`, title: "이 명령을 실행해도 될까요?", kind: permissionKindOf(String(d.command ?? "")), detail: String(d.command ?? "") },
        });
        break;
      }
      case "skipped": {
        const reason = String(d.reason ?? "");
        const a = d.command !== undefined ? byCommand(d.command) : undefined;
        const text = String(d.command ?? reason);
        if (a) upsert({ ...a, status: "skipped", reason });
        else upsert({ id: `a${++n}`, label: text, status: "skipped", reason });
        if (a && a.id === runningId) runningId = null;
        skipped.push({ text, reason });
        emit({ type: "permission", request: null });
        break;
      }
      case "error": {
        const code = d.exit_code !== undefined && d.exit_code !== null ? ` (종료 코드 ${String(d.exit_code)})` : "";
        const reason = `${String(d.reason ?? "실패했습니다")}${code}`;
        const a = actions.find((x) => x.id === runningId) ?? actions[actions.length - 1];
        const detail = d.output ? { kind: "output" as const, text: String(d.output) } : undefined;
        if (a) upsert({ ...a, status: "failed", reason, ...(detail ? { detail } : {}) });
        else upsert({ id: `a${++n}`, label: "작업", status: "failed", reason, ...(detail ? { detail } : {}) });
        runningId = null;
        break;
      }
      case "summary": {
        const files = Array.isArray(d.files) ? d.files : [];
        const summary: WorkSummary = {
          did: d.text ? [String(d.text)] : [],
          files: files.map((f) => {
            if (typeof f === "string") return { name: f, change: "수정" as const };
            const o = f as Json;
            const c = String(o.change ?? "");
            return { name: String(o.name ?? o.path ?? ""), change: c === "추가" || c === "삭제" ? (c as "추가" | "삭제") : ("수정" as const) };
          }),
          skipped,
          usage: [], // the server sends no free-limit numbers yet
        };
        summarySent = true;
        emit({ type: "summary", summary });
        break;
      }
      case "done": {
        const error = String(d.error ?? "");
        const result = String(d.result ?? "");
        finishRunning(error ? "skipped" : "done", error ? "작업이 끝났습니다." : undefined);
        if (error) {
          if (!actions.some((a) => a.status === "failed")) upsert({ id: `a${++n}`, label: "작업이 실패했습니다", status: "failed", reason: error });
          emit({ type: "state", state: "failed" });
        } else {
          emit({ type: "state", state: "done" });
          if (!summarySent && result) emit({ type: "summary", summary: { did: [result], files: [], skipped, usage: [] } });
        }
        break;
      }
    }
  }

  return {
    handle,
    /** Local failure (could not create the task, stream broke): shown as a failed row. */
    failed(label: string, reason: string, state: "failed" | "working" = "failed") {
      finishRunning("skipped", "중단되었습니다.");
      upsert({ id: `a${++n}`, label, status: "failed", reason });
      emit({ type: "state", state });
    },
    stopped() {
      finishRunning("skipped", "멈췄습니다.");
      emit({ type: "state", state: "stopped" });
    },
  };
}

/** Reads an SSE response and calls onEvent(event, data) for every complete block. */
async function readSse(res: Response, onEvent: (event: string, data: Json) => void): Promise<void> {
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
      const data = [...block.matchAll(/^data: ?(.*)$/gm)].map((m) => m[1]).join("\n");
      if (!ev || !data) continue; // comments / keep-alive
      try {
        const parsed = JSON.parse(data);
        onEvent(ev, parsed && typeof parsed === "object" ? (parsed as Json) : { value: parsed });
      } catch {
        /* a broken block is skipped */
      }
    }
  }
}

function explain(err: unknown): string {
  const status = (err as { status?: number })?.status;
  if ((err as Error)?.message === "unauthorized" || status === 401) return "다시 로그인해 주세요.";
  if (status === 502 || status === 503) return "서버가 지금 작업을 받을 수 없습니다. 잠시 뒤에 다시 시도해 주세요.";
  if (status) return `서버가 요청을 받지 못했습니다 (오류 ${status}).`;
  return "서버에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.";
}

export type SseSourceOptions = { prompt: string; mode: PermissionMode; conversationId?: string };

/** Real source for Work mode: starts the task on the server and follows its events. */
export function sseSource(opts: SseSourceOptions): TaskSource {
  return {
    connect(emit): TaskConnection {
      const ctrl = new AbortController();
      const map = makeMapper(emit);
      emit({ type: "meta", mode: opts.mode, elapsed: 0 });
      emit({ type: "state", state: "working" });

      const taskId: Promise<string | null> = createTask(opts.prompt, TO_SERVER[opts.mode], opts.conversationId ?? "")
        .then((t) => t.id)
        .catch((err) => {
          map.failed("작업을 시작하지 못했습니다", explain(err));
          return null;
        });

      void taskId.then(async (id) => {
        if (!id) return;
        try {
          const res = await taskEvents(id, ctrl.signal);
          await readSse(res, (event, data) => map.handle(event, data));
        } catch (err) {
          if (ctrl.signal.aborted) return;
          map.failed("서버와 연결이 끊겼습니다", `${explain(err)} 작업은 서버에서 계속될 수 있습니다.`, "working");
        }
      });

      return {
        stop() {
          void taskId.then(async (id) => {
            if (!id) return;
            try {
              await stopTask(id);
            } finally {
              map.stopped();
            }
          });
        },
        interject(text) {
          void taskId.then(async (id) => {
            if (!id) return;
            await messageTask(id, text).catch(() => map.failed("끼어들기를 보내지 못했습니다", "작업이 끝났거나 서버에 연결할 수 없습니다.", "working"));
          });
        },
        answerPermission(_requestId: string, answer: PermissionAnswer) {
          void taskId.then(async (id) => {
            if (!id) return;
            await decideTaskPermission(id, answer === "once" ? "allow" : answer).catch(() => map.failed("허락을 전하지 못했습니다", "서버에 연결할 수 없습니다.", "working"));
          });
        },
        rewind() {
          // No server endpoint yet (listed in the report). The screen still offers it; nothing happens on the server.
        },
        setMode(mode) {
          // No server endpoint to change the mode of a running task yet: only the chip changes.
          emit({ type: "meta", mode });
        },
        close() {
          ctrl.abort();
        },
      };
    },
  };
}
