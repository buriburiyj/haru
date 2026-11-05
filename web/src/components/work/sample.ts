import type { WorkFile, WorkRun } from "./types";

// Example data for ?demo=work. Replaced by server data later.

export const SAMPLE_RUN_WORKING: WorkRun = {
  computer: "box",
  mode: "auto",
  state: "working",
  elapsed: 192,
  todos: [
    { id: "t1", text: "저장소 구조 파악하기", done: true },
    { id: "t2", text: "README 초안 쓰기", done: true },
    { id: "t3", text: "테스트 돌려 보기", done: false },
    { id: "t4", text: "결과를 jun-lab에 올리기 (push는 허락 필요)", done: false },
  ],
  actions: [
    { id: "a1", label: "jun-lab 파일 목록 읽기", status: "done", detail: { kind: "output", text: "README.md\nscripts/run.py\ndocs/\n3 files" }, checkpoint: true },
    { id: "a2", label: "README.md 수정", status: "done", detail: { kind: "diff", text: "-# jun-lab\n+# jun-lab\n+\n+연구 기록과 실험 스크립트를 모아 둔 저장소입니다.\n 사용법은 아래를 보세요." }, checkpoint: true },
    { id: "a3", label: "npm test 실행", status: "failed", reason: "테스트 2개가 실패했습니다 (api.test.ts: 응답 시간 초과). 설정을 바꿔 다시 시도합니다.", detail: { kind: "output", text: "FAIL src/api.test.ts\n  ✕ returns list (5004 ms)\n  ✕ handles 404 (5001 ms)\nTests: 2 failed, 8 passed" } },
    { id: "a4", label: "테스트 제한 시간을 10초로 늘려 다시 실행", status: "running" },
    { id: "a5", label: "텔레그램으로 중간 보고 보내기", status: "pending", outward: true },
  ],
};

export const SAMPLE_RUN_DONE: WorkRun = {
  computer: "actions",
  mode: "quiet",
  state: "done",
  elapsed: 487,
  todos: [
    { id: "t1", text: "저장소 구조 파악하기", done: true },
    { id: "t2", text: "README 초안 쓰기", done: true },
    { id: "t3", text: "테스트 돌려 보기", done: true },
    { id: "t4", text: "결과를 jun-lab에 올리기", done: true },
  ],
  actions: [
    { id: "a1", label: "jun-lab 파일 목록 읽기", status: "done", checkpoint: true },
    { id: "a2", label: "README.md 수정", status: "done", checkpoint: true, detail: { kind: "diff", text: "+연구 기록과 실험 스크립트를 모아 둔 저장소입니다." } },
    { id: "a3", label: "npm test 실행", status: "done", detail: { kind: "output", text: "Tests: 10 passed" } },
    { id: "a4", label: "jun-lab에 push", status: "skipped", reason: "묻지 않음 모드에서는 미리 허락하지 않은 push를 건너뜁니다.", outward: true },
    { id: "a5", label: "텔레그램으로 완료 보고 보내기", status: "done", outward: true },
  ],
  summary: {
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
  },
};

export const SAMPLE_FILES: WorkFile[] = [
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
  {
    name: "notes.md",
    kind: "문서",
    path: ".agent/work/demo-chat/notes.md",
    versions: [{ when: "방금", lang: "md", text: "# 메모\n\n- 첫 번째 항목\n- 두 번째 항목\n" }],
  },
];
