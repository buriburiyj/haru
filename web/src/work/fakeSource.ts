import type { Computer, PermissionAnswer, PermissionMode, TaskConnection, TaskEvent, TaskSource, Todo, WorkAction, WorkFile, WorkSummary } from "./types";

// Fake task source: example data pushed with delays, for ?demo=work. Replace with the real SSE source later.

export type FakeScenario = "working" | "ask" | "failed" | "done";

const TODOS: Todo[] = [
  { id: "t1", text: "저장소 구조 파악하기", done: true },
  { id: "t2", text: "README 초안 쓰기", done: true },
  { id: "t3", text: "테스트 돌려 보기", done: false },
  { id: "t4", text: "결과를 jun-lab에 올리기 (push는 허락 필요)", done: false },
];

const A1: WorkAction = { id: "a1", label: "jun-lab 파일 목록 읽기", status: "done", detail: { kind: "output", text: "README.md\nscripts/run.py\ndocs/\n3 files" }, checkpoint: true };
const A2: WorkAction = {
  id: "a2",
  label: "README.md 수정",
  status: "done",
  detail: { kind: "diff", text: "-# jun-lab\n+# jun-lab\n+\n+연구 기록과 실험 스크립트를 모아 둔 저장소입니다.\n 사용법은 아래를 보세요." },
  checkpoint: true,
};
const A3_FAILED: WorkAction = {
  id: "a3",
  label: "npm test 실행",
  status: "failed",
  reason: "테스트 2개가 실패했습니다 (api.test.ts: 응답 시간 초과). 설정을 바꿔 다시 시도합니다.",
  detail: { kind: "output", text: "FAIL src/api.test.ts\n  ✕ returns list (5004 ms)\n  ✕ handles 404 (5001 ms)\nTests: 2 failed, 8 passed" },
};
const A4_RUNNING: WorkAction = { id: "a4", label: "테스트 제한 시간을 10초로 늘려 다시 실행", status: "running" };
const A5_PENDING: WorkAction = { id: "a5", label: "텔레그램으로 중간 보고 보내기", status: "pending", outward: true };

const SUMMARY: WorkSummary = {
  did: ["저장소 구조를 읽었습니다.", "README.md 초안을 썼습니다.", "테스트 10개를 모두 통과시켰습니다.", "완료를 텔레그램으로 알렸습니다."],
  files: [
    { name: "README.md", change: "수정" },
    { name: "docs/usage.md", change: "추가" },
  ],
  skipped: [{ text: "jun-lab에 push", reason: "미리 허락하지 않았습니다. 허락하면 이어서 올립니다." }],
  usage: [
    { label: "GitHub Actions", value: "8분 (이번 달 1,500분 중 214분)" },
    { label: "Groq 호출", value: "오늘 12회" },
    { label: "NVIDIA 호출", value: "오늘 0회" },
  ],
};

const FILES: WorkFile[] = [
  {
    name: "report.html",
    kind: "HTML",
    path: ".agent/work/demo-chat/report.html",
    versions: [
      { when: "10분 전", lang: "html", text: "<h1>주간 보고</h1>\n<p>첫 번째 초안입니다.</p>" },
      { when: "5분 전", lang: "html", text: "<h1>주간 보고</h1>\n<p>표를 추가했습니다.</p>\n<table><tr><td>항목</td><td>값</td></tr></table>" },
      { when: "방금", lang: "html", text: "<h1>주간 보고</h1>\n<p>요약과 표를 정리한 최종본입니다.</p>\n<button onclick=\"this.textContent='확인했습니다'\">확인</button>" },
    ],
  },
  { name: "notes.md", kind: "문서", path: ".agent/work/demo-chat/notes.md", versions: [{ when: "방금", lang: "md", text: "# 메모\n\n- 첫 번째 항목\n- 두 번째 항목\n" }] },
];

export function fakeSource(scenario: FakeScenario, computer: Computer = "box"): TaskSource {
  return {
    connect(emit) {
      const timers: number[] = [];
      let live = true;
      let mode: PermissionMode = scenario === "done" ? "quiet" : "auto";
      let running: WorkAction | null = null;
      const send = (e: TaskEvent) => {
        if (live) emit(e);
      };
      const at = (ms: number, e: TaskEvent | (() => void)) => {
        timers.push(window.setTimeout(() => (typeof e === "function" ? e() : send(e)), ms));
      };

      const snapshot = (elapsed: number, state: "working" | "done" | "failed", actions: WorkAction[], todos: Todo[]) => {
        send({ type: "meta", computer, mode, elapsed });
        send({ type: "state", state });
        send({ type: "todos", todos });
        actions.forEach((a) => send({ type: "action", action: a }));
      };

      if (scenario === "done") {
        snapshot(487, "done", [A1, A2, { id: "a3", label: "npm test 실행", status: "done", detail: { kind: "output", text: "Tests: 10 passed" } }, { id: "a4", label: "jun-lab에 push", status: "skipped", reason: "묻지 않음 모드에서는 미리 허락하지 않은 push를 건너뜁니다.", outward: true }, { id: "a5", label: "텔레그램으로 완료 보고 보내기", status: "done", outward: true }], TODOS.map((t) => ({ ...t, done: true })));
        send({ type: "summary", summary: SUMMARY });
        send({ type: "files", files: FILES });
      } else if (scenario === "failed") {
        snapshot(240, "failed", [A1, A2, A3_FAILED, { ...A4_RUNNING, status: "failed", reason: "다시 실행한 테스트도 실패했습니다. 3번 시도해 보고 멈춥니다." }], TODOS);
      } else {
        running = A4_RUNNING;
        snapshot(192, "working", [A1, A2, A3_FAILED, A4_RUNNING, A5_PENDING], TODOS);
        if (scenario === "ask") {
          at(300, { type: "permission", request: { id: "p1", title: "GitHub: jun-lab에 파일 3개 올리기", kind: "normal", detail: "파일 3개: README.md, docs/usage.md, scripts/run.py" } });
        } else {
          // working: finishes by itself after about 30 s
          at(8000, () => {
            send({ type: "action", action: { ...A4_RUNNING, status: "done", detail: { kind: "output", text: "Tests: 10 passed" } } });
            send({ type: "todos", todos: TODOS.map((t) => (t.id === "t3" ? { ...t, done: true } : t)) });
            running = { id: "a6", label: "README.md 최종본 저장", status: "running" };
            send({ type: "action", action: running });
          });
          at(18000, () => {
            send({ type: "action", action: { id: "a6", label: "README.md 최종본 저장", status: "done", checkpoint: true } });
            send({ type: "action", action: { ...A5_PENDING, status: "done" } });
            send({ type: "todos", todos: TODOS.map((t) => ({ ...t, done: true })) });
            send({ type: "summary", summary: SUMMARY });
            send({ type: "files", files: FILES });
            send({ type: "state", state: "done" });
            running = null;
          });
        }
      }

      const conn: TaskConnection = {
        stop() {
          if (running) send({ type: "action", action: { ...running, status: "skipped", reason: "멈췄습니다." } });
          running = null;
          send({ type: "state", state: "stopped" });
        },
        interject(text, id) {
          at(1500, { type: "action", action: { id, label: text, status: "running", interjection: true } });
          at(4500, { type: "action", action: { id, label: text, status: "done" } });
        },
        answerPermission(_id: string, answer: PermissionAnswer) {
          send({ type: "permission", request: null });
          if (answer === "deny") {
            send({ type: "action", action: { id: "a-push", label: "jun-lab에 push", status: "skipped", reason: "허락하지 않아 건너뛰었습니다.", outward: true } });
          } else {
            send({ type: "action", action: { id: "a-push", label: "jun-lab에 push", status: "done", outward: true } });
          }
        },
        rewind(actionId) {
          send({ type: "action", action: { id: `rewind-${actionId}`, label: "체크포인트로 되돌렸습니다", status: "done" } });
        },
        setMode(next) {
          mode = next;
          send({ type: "meta", mode: next });
        },
        close() {
          live = false;
          timers.forEach((t) => window.clearTimeout(t));
        },
      };
      return conn;
    },
  };
}
