// Types for the work (진행) screens. Example data only: no server yet (SPEC "단기목표 확정").

/** The 6 permission modes (same as Claude). */
export type PermissionMode = "ask" | "auto-edit" | "plan" | "auto" | "quiet" | "all";

export const MODE_LABEL: Record<PermissionMode, string> = {
  ask: "매번 확인",
  "auto-edit": "수정 자동",
  plan: "계획",
  auto: "자동",
  quiet: "묻지 않음",
  all: "전부 허용",
};

export const MODE_HINT: Record<PermissionMode, string> = {
  ask: "모든 행동을 하기 전에 물어봅니다",
  "auto-edit": "파일 수정은 알아서 하고, 나머지는 물어봅니다",
  plan: "먼저 계획만 세우고, 승인하면 실행합니다",
  auto: "위험한 행동은 검사 모델이 확인합니다 (기본)",
  quiet: "미리 허락한 것만 하고, 건너뛴 일은 끝나고 알려 줍니다 (예약 작업 기본)",
  all: "격리된 컴퓨터(GitHub Actions, Codespaces)에서만 쓸 수 있습니다",
};

export const MODE_ORDER: PermissionMode[] = ["ask", "auto-edit", "plan", "auto", "quiet", "all"];

export type Computer = "box" | "tab" | "actions" | "codespaces";
export const COMPUTER_LABEL: Record<Computer, string> = {
  box: "맥 (box)",
  tab: "탭 S6",
  actions: "GitHub Actions",
  codespaces: "Codespaces",
};
/** "전부 허용" is only allowed on isolated computers. */
export const ISOLATED: Record<Computer, boolean> = { box: false, tab: false, actions: true, codespaces: true };

export type StepStatus = "done" | "running" | "failed" | "skipped" | "pending";

export type Todo = { id: string; text: string; done: boolean };

export type ActionDetail = { kind: "output"; text: string } | { kind: "diff"; text: string };

export type WorkAction = {
  id: string;
  /** one line: "README.md 읽기", "npm test 실행" */
  label: string;
  status: StepStatus;
  detail?: ActionDetail;
  /** why it failed or was skipped */
  reason?: string;
  /** sent something outside (message, email, push, deploy): cannot be undone */
  outward?: boolean;
  /** a checkpoint was saved after this action */
  checkpoint?: boolean;
  /** user interjection waiting for the current step to end */
  interjection?: boolean;
};

export type WorkSummary = {
  did: string[];
  files: { name: string; change: "추가" | "수정" | "삭제" }[];
  skipped: { text: string; reason: string }[];
  usage: { label: string; value: string }[];
};

export type RunState = "working" | "done" | "failed" | "stopped";

export type WorkRun = {
  /** conversation id; known as soon as the server answered POST /tasks */
  chatId?: string;
  computer: Computer;
  mode: PermissionMode;
  state: RunState;
  /** seconds since start (the screen only shows it) */
  elapsed: number;
  todos: Todo[];
  actions: WorkAction[];
  summary?: WorkSummary;
};

export function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}분 ${String(s).padStart(2, "0")}초` : `${s}초`;
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** File card data (결과물 저장). `versions` oldest first. */
export type FileKind = "문서" | "코드" | "HTML" | "표" | "슬라이드" | "PDF" | "차트";
export type FileVersion = { text: string; lang: string; when: string };
export type WorkFile = { name: string; kind: FileKind; path: string; versions: FileVersion[] };

// ---- Task stream (what the progress screen receives). api.ts is NOT imported here. ----

/** A permission request raised while working. Same shape as the permission card needs. */
export type TaskPermission = {
  id: string;
  title: string;
  kind: "normal" | "delete" | "send" | "pay";
  detail?: string;
};
export type PermissionAnswer = "once" | "always" | "deny";

/** Events a task source pushes, in any order. `action` is an upsert by id (append when new). */
export type TaskEvent =
  | { type: "reset" }
  | { type: "meta"; computer?: Computer; mode?: PermissionMode; /** seconds already worked */ elapsed?: number; /** the conversation this task belongs to (server creates one for a new Work request) */ chatId?: string }
  | { type: "state"; state: RunState }
  | { type: "todos"; todos: Todo[] }
  | { type: "action"; action: WorkAction }
  | { type: "permission"; request: TaskPermission | null }
  | { type: "summary"; summary: WorkSummary }
  | { type: "files"; files: WorkFile[] };

/** What the screen can ask of the running task (all go to the server later). */
export type TaskConnection = {
  stop(): void;
  /** `id` is the action id the screen already shows for this interjection */
  interject(text: string, id: string): void;
  answerPermission(requestId: string, answer: PermissionAnswer): void;
  rewind(actionId: string): void;
  setMode(mode: PermissionMode): void;
  close(): void;
};

/**
 * A source of task events. Today: fakeSource (timed example data). Later: one made from the SSE function
 * Codex adds to api.ts. useTask only needs this interface.
 */
export type TaskSource = { connect(onEvent: (e: TaskEvent) => void): TaskConnection };
