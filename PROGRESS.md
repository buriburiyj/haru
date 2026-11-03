# PROGRESS

Last updated: 2026-11-03 (Claude Code, deadline 2026-11-02)

## 진행 중
- [창A] 홈 화면 앱 준비 완료(빌드 통과, 실기기 확인 전): manifest(public/manifest.webmanifest), 아이콘 public/icons/ (180, 192, maskable 192), apple-touch-icon을 index.html에 연결, safe-area 여백(styles/mobile.css, #root), 오프라인 안내(components/OfflineNotice.tsx, 서비스 워커 없음). 512 아이콘은 원본이 ~194px라 만들지 않음(고해상도 원본 필요).
- [창A] 화면 다듬기 완료(빌드 통과, 브라우저 확인 전): 답변 아래 모델 이름 자리(AssistantMessage modelName / ChatView modelNames), 로그인 화면(등록한 기기는 토큰 칸 숨김 + '다른 기기 등록', 오류 4종 components/auth/loginErrors.ts — useAuth가 아직 kind를 안 넘겨서 지금은 일반 문구), 설정 테마·글꼴 크기 localStorage 저장(settings/appearance.ts), 채팅 목록 props형(chats/onDelete/onOpen) + 모든 삭제는 ConfirmDialog 경유
- [창A] 1단계 화면 부분: 완료, 브라우저 확인 전 (2026-11-03)
- [창A] 화면 추가 완료(서버 없이, 임시 데이터): 채팅 목록/프로젝트/아티팩트 페이지, 임시 채팅 토글, 권한 요청 카드. 데모: URL에 ?demo=permission (또는 permission-delete, projects)
- [창A] 수정 범위: web/src/components, styles, design, public만. api.ts, hooks/, server/는 안 건드림
- [창A] 폰: 첫 화면 ☰ 서랍(이벤트), 페이지/팝업 전체화면, visualViewport로 입력창 키보드 위, 터치 44px는 styles/mobile.css(pointer: coarse)
- [창A] 빌드 통과, 색 직접 사용 0건. 폰 점검은 코드로만 함(실기기/390px 눈으로 확인 아직 안 함)

## Done
- [창B] Stage 0 DONE (2026-11-03): Groq/NVIDIA real answers, jun-files .agent save, passkey register+login on Mac against https://haru-server.hostless.app (1a16afb, Hostless env CRED_FILE=/tmp/credentials.json, QUEUE_DIR=/tmp/queue). Auth = signed challenge_id + Bearer token in localStorage (no cookies; cross-site cookies were blocked). jun-files .agent/credentials.json holds 1 credential (public keys only). Defaults for CRED_FILE/QUEUE_DIR are now /tmp and local write failures no longer cause 500. Known: Codex transport not implemented (router falls through to NVIDIA); nemotron-3-ultra gave 503 overload once.
- Codex login works in GitHub Actions (jun-files, secret CODEX_AUTH_JSON, workflow codex-auth-test, run 41319601552 success, 23s). So Actions can use Codex when the Mac is off.
- GitHub Pages live: https://buriburiyj.github.io/haru (200). Token haru-store (jun-files Contents rw, expires 2027-01-30) saved as HARU_GH_TOKEN in ~/computer-use/.env, verified with API 200.
- Repo buriburiyj/haru created and pushed. Box started; both models answered the first exam problem (exam/RESULT.md): inconclusive, order unchanged.
- SPEC.md read. PROGRESS.md and STEPS.md drafted. Local commits only.
- server/ skeleton (FastAPI /health, SSE /chat, router, storage queue, passkey stubs). Only /health and 401 checked; Groq/NVIDIA/GitHub commit/WebAuthn untested.
- web/ empty PWA + .github/workflows/pages.yml. Build passes.

- [창B] Stage 1 server DONE (2026-11-03, be59b0c; NEEDS Hostless deploy): Groq default model is now openai/gpt-oss-20b (llama-3.1-8b-instant was removed by Groq, which made every chat fall to NVIDIA). The "Switching to ..." text is gone from answers; the done event carries model and title. API: GET /models, GET /chats?q=, GET /chats/{id}, POST /chats/{id}/rename, DELETE /chats/{id} (call only after UI confirm). One commit per answer holds the chat file + .agent/chats/index.json. Types are in web/src/api.ts. useAuth now reports LoginError kinds via classifyLoginError. Env: optional GITHUB_BRANCH (default main).

## Web UI skeleton (2026-11-02)
- Foundation done (f020de6): Tailwind v4 (@tailwindcss/vite), Pretendard bundled via npm `pretendard` (no CDN), web/src/styles/tokens.css (TEMP neutral colors, accent #DA7756), components/Logo.tsx (temp SVG, replace with icon.png later).
- Old App.tsx logic was ABSORBED, not dropped: passkey login/register -> hooks/useAuth.ts; SSE chat send/stream/notice -> hooks/useChat.ts; login form -> components/LoginScreen.tsx; api.ts untouched. web/src/styles.css deleted (replaced by index.css + tokens.css; its .bubble/.home/.prompt classes are gone, superseded by Tailwind components).
- UI skeleton built (static, build passes, no raw colors, NOT opened in a browser yet): Sidebar+Welcome, Composer (+ menu, model menu, effort), ChatView. Still placeholder: + submenu items, web search toggle (local state only), file upload, / skills list, user message time fixed to '방금', recent chats list empty, Sidebar Chat/Code tab does nothing.
- Owners (done): Sidebar.tsx+Welcome.tsx (sidebar agent), Composer.tsx (composer agent), ChatView.tsx (chat agent); App.tsx assembles. Server link (VITE_API_URL) belongs to the other session.

- Tokens confirmed from reference.html (light/dark values, accent #DA7756, 6px scrollbar); no raw colors in components. Logo = transparent PNG (src/assets/logo.png), favicon.svg, apple-touch-icon 180, PWA icon 192 (any + maskable).
- NEED HIGH-RES ICON ORIGINAL (고해상도 원본 필요): icon_transparent.png only has a ~194px icon, so no 512px PWA icon was made (not upscaled). web/design/icon_raw.png is a 59-byte JSON file, unused, not committed.

- [창A] Stage 1 screens (static, build passes, no raw colors, NOT yet viewed in a browser): markdown renderer (own, no dependency; code blocks + copy, tables, lists), <think> fold (Thinking.tsx), ArtifactPanel (right pane, phone fullscreen, sandboxed iframe), message edit keeps versions with ‹ 1/2 › (local state only; real tree comes with the server), Settings (⌘,) and Search (⌘K) shells via Overlays.tsx mounted in Sidebar, no billing tab. Placeholders: all sample data, branch/edit not persisted, thinking comes from <think> tags until the server sends it.

## Blocked
- (resolved) Hostless: junbot DELETED (user approved); haru-server created at https://haru-server.hostless.app, $0.00, deploys from repo haru/server on main, /health 200, /chat without session 401 (verified with curl). Size shows Standard (0.5 vCPU/1GiB) on the scaling page; confirm it is intended and still $0.00. Env vars NOT entered yet (needs GROQ_API_KEY, NVIDIA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, HARU_GH_TOKEN as GITHUB_TOKEN, SESSION_SECRET, SETUP_TOKEN; Aside cannot read the real ~/computer-use/.env, so the user must paste values or use the Import .env button).
- Aside session GYBNT6BZg9A08Sez finished haru-server and a read-only check of https://buriburiyj.github.io/haru/ (loads, light/dark OK, 390px OK, no visible bugs).

## Remaining
- Exam order stays gpt-6-luna -> gpt-5.6-terra -> gpt-5.6-luna (both 13/13)
- Stages 1-6 per SPEC.md section 12

## Next (one line)
Stage 1 server side (real chat save, chat list API, auto model selection wiring): plan reported, waiting for approval.
- [창A] 2단계 화면(서버 없이): components/customize/ (CustomizePanel 하나를 사이드바 사용자 지정 팝업과 설정 팝업이 공유). 임시 예시 데이터는 customize/sample.ts.
- [창A] [Skills|커넥터|플러그인]x[내 항목|탐색], 빈 상태 카드, 커넥터 표(이름/유형/상태), Skills 목록(⋯ 메뉴). 서버 연결과 저장은 아직 없음.
- [창A] web/design/icon_raw.png 삭제함. 아이콘은 icon_transparent.png 기준으로 이미 반영됨(로고 PNG, favicon.svg, apple-touch 180, PWA 192 any+maskable).
- [창A] 빌드 통과, 색 직접 사용 0건. 브라우저에서 직접 열어 보는 확인은 아직 안 함.
