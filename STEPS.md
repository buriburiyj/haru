# STEPS

Owner: Claude Code builds every stage (SPEC.md "작업 분담 변경"). Aside does browser work only (Hostless/GitHub settings screens, checking finished screens).
Quality first, no rush. After EACH stage: stop, report in 3 lines (what was done, how the user can check it by hand), wait for the user's OK before the next stage.
Always: never print keys (secrets only in ~/computer-use/.env, Hostless env, GitHub Secrets). Stop at any payment or paid-option screen. One owner per folder when using subagents; commit only own paths; `git pull --rebase` before push.
Each stage ends with: tests pass + the thing is actually seen working + commit + push + PROGRESS.md updated.

Already done (see PROGRESS.md): exam (order kept), Codex works in Actions, Pages live, haru-server deployed on Hostless ($0.00), web UI skeleton with confirmed tokens/icons.

## Stage 0 - Real server connection
Steps
0.1 Enter env vars in Hostless (user pastes values or uses "Import .env"; Aside only clicks): GROQ_API_KEY, NVIDIA_API_KEY, GITHUB_TOKEN (= HARU_GH_TOKEN), SESSION_SECRET (random 32+ bytes), SETUP_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Never call getUpdates with the bot token.
0.2 Web build gets VITE_API_URL=https://haru-server.hostless.app (GitHub Actions variable, not a secret). Confirm CORS only allows https://buriburiyj.github.io and cookies work cross-site (SameSite=None, Secure).
0.3 Router: Groq classify -> Codex (gpt-6-luna -> gpt-5.6-terra -> gpt-5.6-luna) -> NVIDIA chain; one-line notice when it falls to the next model; wait and retry on 429. Codex path: dispatch a job on GitHub Actions (jun-files, secret CODEX_AUTH_JSON) or box when the Mac is on.
0.4 Storage: after each answer, one commit to jun-files/.agent/chats/<id>.json; failure queues on the server and retries.
0.5 Passkey register (with SETUP_TOKEN) and login on the real iPhone/Mac browser.
Done when (완료 기준)
- `pytest server/tests` passes; `curl https://haru-server.hostless.app/health` -> ok; `/chat` without session -> 401.
- On https://buriburiyj.github.io/haru/ the user registers a passkey, logs in with Face ID/Touch ID, sends "안녕", and sees a streamed Korean polite answer.
- A file for that chat appears in jun-files/.agent/chats/. Forcing a Groq failure shows the "다음 모델로 넘어갑니다" one-liner and still answers.
- Hostless stays $0.00 and memory <= 150MB (check the Hostless usage page).

## Stage 1 - Chat complete
Steps
1.1 Streaming polish: stop button, send-while-running (applies after the current step), next-prompt suggestion (gray, Tab fills, Groq, can be turned off).
1.2 Thinking section: collapsed by default, click to expand.
1.3 Branches: edit/regenerate keeps old versions, "‹ 2/3 ›" switcher (data model in chat file: message tree).
1.4 Artifacts: right pane (full screen on phone), sidebar Artifacts tab, code/web page/document preview, [Haru로 고치기] on error.
1.5 Conversation list + search over all chats (index.json), rename/delete (delete asks first), projects with separate memory.
1.6 Memory: auto topic saving, "기억해" saves now, "기억 업데이트됨" chip, settings page to view/edit/delete; secret chat (ghost) saves nothing.
1.7 Files/photos (nemotron vision), web search (DuckDuckGo -> Tavily, sources shown), styles (기본/간결/자세히), model picker wired to the router.
Done when
- Unit tests for branches, search, memory pass; `npm run build` passes; no raw colors (grep).
- User sees: streamed answer with a collapsed thinking block; edit a message and flip between versions; an HTML artifact rendered in the right pane; a search finds text inside an old chat; "기억해 ..." shows the chip and the item in Settings -> Memory; a secret chat leaves no file in jun-files.
- Aside confirms the same screens at 390px width in light and dark.

## Stage 2 - Customize (Skills / Connectors / Plugins)
Steps
2.1 Skills: folder with SKILL.md (+ optional scripts) in jun-files/.agent/skills/, Claude-skill compatible import, name+description loaded first only; "/" lists skills; create-skill asks first (setting "알아서 만들기").
2.2 Plugins: bundle of skills+connectors+commands, install/remove as one unit.
2.3 Connectors (MCP style, settings only in jun-files, keys on the server): Gmail (app password), GitHub (new fine-grained token), Google Drive (OAuth; decide the 7-day test-mode re-login fix), Notion (internal token). "○○ 다시 연결해 주세요" when expired.
2.4 Permissions UI: [이번만 허용][항상 허용][거부] saved in permissions.json, revocable in Settings; delete/send/pay ask every time even if "always".
Done when
- Tests for SKILL.md parsing, permission rules (always-allow never skips delete/send/pay), connector token expiry pass.
- User sees: install a public Claude skill by URL and run it with "/"; each of the 4 connectors shows ✓ after connect and answers one real read-only request (e.g. "최근 메일 3개 제목"); revoking "항상 허용" in Settings makes it ask again.
- Browser steps for tokens/OAuth are done by Aside from short briefs written in this file; no payment screen reached.

## Stage 3 - Code tab
Steps
3.1 Sidebar for Code: new session / routines / customize / recent sessions; chips for run location (Actions | box), repo, branch.
3.2 Four modes: Manual / Auto-edit / Plan / Auto (Auto: Groq checks risk, delete/send always ask). Plan mode: [자동으로 진행][하나씩 승인][계속 계획].
3.3 Execution on GitHub Actions (public work in haru, private in jun-files) or box when the Mac is on; live terminal over SSE.
3.4 Diff view ("+12 -1", per-file, line comments sent together), checkpoints and rewind, session info (location, changed files, running tasks, context %).
Done when
- Tests for mode rules and checkpoint rewind pass.
- User sees: pick a repo, ask for a small change in Plan mode, approve, watch the live terminal, view the diff, rewind to the checkpoint and the file returns; Actions minutes remaining shown in Settings -> Usage.

## Stage 4 - Cowork
Steps
4.1 Task checklist UI; folder (jun-files path) picked, runs in the background, asks only when needed.
4.2 Word/PPT/Excel/PDF generation (Actions); PDF via the pdf skill route.
4.3 Browser control with per-site [이번만][항상][거부]; payment, account creation and captcha always handed to the user.
Done when
- Tests for the checklist state machine pass.
- User sees: a request like "이 폴더 요약해서 PPT로" shows a checklist, produces a downloadable file, and a browser task stops and asks at a login/payment page.

## Stage 5 - Mac app (Swift, Command Line Tools only)
Steps
5.1 Swift wrapper (WKWebView) built with swiftc/`swift build`, no Xcode; loads https://buriburiyj.github.io/haru/.
5.2 Shortcuts (Option twice quick launch), file search, screen control permission asked once per task.
5.3 Settings -> This device section only inside the Mac app.
Done when
- `swift build` succeeds; the .app opens, shows the same UI, passkey login works inside it.
- User sees: Option twice opens a floating input; screen-control asks once, "항상 허용" stops asking.

## Stage 6 - Scheduled tasks
Steps
6.1 schedules/ files, cron-like runner on the active server, quiet hours 23:00-07:00.
6.2 Proactive messages, skill auto-creation setting, push notifications (PWA, fallback Telegram sendMessage only).
6.3 Standby server (Serv00 when approved) with lease in jun-files/.agent/lease (owner + expiry, takeover within 1 minute).
Done when
- Tests for lease takeover and quiet hours pass.
- User sees: a schedule fires on time and a notification arrives; stopping the main server makes the standby take over within 1 minute; nothing is sent between 23:00 and 07:00.

## Aside browser briefs (copy as the prompt)
Done: Hostless app (haru-server), GitHub Pages, token haru-store.
Stage 0.1: "On the Hostless app haru-server -> Environment, click Import .env or Add variable and fill ONLY names I give you; I will paste the values myself. Do not display values. Stop at any payment screen."
Verification brief: "Open <url> at 390px width in light and dark, list anything cut off, overlapping or broken. Change nothing."
