# PROGRESS

Last updated: 2026-11-03 (Claude Code, deadline 2026-11-02)

## Done
- Codex login works in GitHub Actions (jun-files, secret CODEX_AUTH_JSON, workflow codex-auth-test, run 41319601552 success, 23s). So Actions can use Codex when the Mac is off.
- GitHub Pages live: https://buriburiyj.github.io/haru (200). Token haru-store (jun-files Contents rw, expires 2027-01-30) saved as HARU_GH_TOKEN in ~/computer-use/.env, verified with API 200.
- Repo buriburiyj/haru created and pushed. Box started; both models answered the first exam problem (exam/RESULT.md): inconclusive, order unchanged.
- SPEC.md read. PROGRESS.md and STEPS.md drafted. Local commits only.
- server/ skeleton (FastAPI /health, SSE /chat, router, storage queue, passkey stubs). Only /health and 401 checked; Groq/NVIDIA/GitHub commit/WebAuthn untested.
- web/ empty PWA + .github/workflows/pages.yml. Build passes.

## Web UI skeleton (2026-11-02)
- Foundation done (f020de6): Tailwind v4 (@tailwindcss/vite), Pretendard bundled via npm `pretendard` (no CDN), web/src/styles/tokens.css (TEMP neutral colors, accent #DA7756), components/Logo.tsx (temp SVG, replace with icon.png later).
- Old App.tsx logic was ABSORBED, not dropped: passkey login/register -> hooks/useAuth.ts; SSE chat send/stream/notice -> hooks/useChat.ts; login form -> components/LoginScreen.tsx; api.ts untouched. web/src/styles.css deleted (replaced by index.css + tokens.css; its .bubble/.home/.prompt classes are gone, superseded by Tailwind components).
- UI skeleton built (static, build passes, no raw colors, NOT opened in a browser yet): Sidebar+Welcome, Composer (+ menu, model menu, effort), ChatView. Still placeholder: + submenu items, web search toggle (local state only), file upload, / skills list, user message time fixed to '방금', recent chats list empty, Sidebar Chat/Code tab does nothing.
- Owners (done): Sidebar.tsx+Welcome.tsx (sidebar agent), Composer.tsx (composer agent), ChatView.tsx (chat agent); App.tsx assembles. Server link (VITE_API_URL) belongs to the other session.

- Tokens confirmed from reference.html (light/dark values, accent #DA7756, 6px scrollbar); no raw colors in components. Logo = transparent PNG (src/assets/logo.png), favicon.svg, apple-touch-icon 180, PWA icon 192 (any + maskable).
- NEED HIGH-RES ICON ORIGINAL (고해상도 원본 필요): icon_transparent.png only has a ~194px icon, so no 512px PWA icon was made (not upscaled). web/design/icon_raw.png is a 59-byte JSON file, unused, not committed.

## Blocked
- (resolved) Hostless: junbot DELETED (user approved); haru-server created at https://haru-server.hostless.app, $0.00, deploys from repo haru/server on main, /health 200, /chat without session 401 (verified with curl). Size shows Standard (0.5 vCPU/1GiB) on the scaling page; confirm it is intended and still $0.00. Env vars NOT entered yet (needs GROQ_API_KEY, NVIDIA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, HARU_GH_TOKEN as GITHUB_TOKEN, SESSION_SECRET, SETUP_TOKEN; Aside cannot read the real ~/computer-use/.env, so the user must paste values or use the Import .env button).
- Aside session GYBNT6BZg9A08Sez finished haru-server and a read-only check of https://buriburiyj.github.io/haru/ (loads, light/dark OK, 390px OK, no visible bugs).

## Remaining
- Exam order stays gpt-6-luna -> gpt-5.6-terra -> gpt-5.6-luna (both 13/13)
- Stage 0 skeleton: test Groq/NVIDIA/GitHub commit/passkey for real; set SESSION_SECRET
- Hostless app + env vars (STEPS C1; Aside cannot read the real ~/computer-use/.env, so a human or a clipboard step must supply values)
- Stages 1-6 per SPEC.md section 12

## Next (one line)
Enter the env vars in Hostless (user pastes values), set VITE_API_URL=https://haru-server.hostless.app for the web build, then test passkey register/login and /chat end to end.
