# STEPS

Rules: see SPEC.md section 1 (0 won, never print keys, stop at any payment screen).
Each step: who runs it, command, success check. "Mac" = user pastes into Mac terminal. "Aside" = Aside runs it.
Secrets live only in ~/computer-use/.env.

## A. Stage 0 exam
A1. (Mac or Aside) Check box is up: `limactl list` -> "box" Running. If not: `limactl start box`.
A2. (Mac) Same coding problem to both models in box; compare pass/fail and time.
    Success: a table in `exam/RESULT.md` with winner order for gpt-6-luna vs gpt-5.6-terra.
A3. (Aside) Test Codex login in GitHub Actions on a private repo (jun-files): workflow that runs `codex --version`
    using an auth secret. Success: green run. If it fails, record "NVIDIA takes over when Mac is off" in PROGRESS.md.
A4. Update SPEC order (section 4) in PROGRESS.md only; do not edit SPEC.md.

## B. Stage 0 skeleton (code in this repo)
B1. server/ FastAPI `GET /health`. Check: `cd server && pip install -r requirements.txt && uvicorn main:app` then `curl localhost:8000/health` -> ok.
B2. Model router (Groq classify -> Codex -> NVIDIA fallback), SSE `POST /chat`. Check: curl -N shows streamed chunks.
B3. .agent storage via GitHub API to jun-files (commit per answer, local retry queue). Check: a test chat file appears in jun-files/.agent/chats/.
B4. Passkey login (WebAuthn, rpId buriburiyj.github.io, origin https://buriburiyj.github.io). Check: register + login in browser; API returns 401 without session.
B5. web/ Vite + React + TS empty PWA (manifest, service worker, greeting + empty input). Check: `cd web && npm run build` succeeds.
B6. GitHub Pages deploy workflow. Check: https://buriburiyj.github.io/haru loads.

## C. Aside browser briefs (copy each as the prompt to Aside)
C1 Hostless app:
  "In Hostless (logged in), create a NEW web app named haru-server (do not touch worker junbot). Python FastAPI, free plan.
   Connect GitHub repo buriburiyj/haru, folder server/. Add env vars GROQ_API_KEY, NVIDIA_API_KEY, TELEGRAM_BOT_TOKEN,
   TELEGRAM_CHAT_ID, GH_TOKEN by reading ~/computer-use/.env; never show values. Deploy once by git push only; no Redeploy clicks.
   If any payment/card screen appears, STOP and report. Report the app URL."
C2 GitHub Pages:
  "On github.com/buriburiyj/haru -> Settings -> Pages, set Source to GitHub Actions. Report the final URL
   (must be https://buriburiyj.github.io/haru)."
C3 Token:
  "Create a NEW fine-grained GitHub token named haru-store: only repo buriburiyj/jun-files, Contents: read/write.
   Do NOT regenerate or delete junbot-files. Save it into ~/computer-use/.env as HARU_GH_TOKEN. Never print it."

## D. Later stages
Stages 1-6 follow SPEC.md section 12. Break each into steps in this file when starting it.
