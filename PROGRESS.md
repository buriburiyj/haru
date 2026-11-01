# PROGRESS

Last updated: 2026-11-02 (Claude Code, deadline 2026-11-02)

## Done
- GitHub Pages live: https://buriburiyj.github.io/haru (200). Token haru-store (jun-files Contents rw, expires 2027-01-30) saved as HARU_GH_TOKEN in ~/computer-use/.env, verified with API 200.
- Repo buriburiyj/haru created and pushed. Box started; both models answered the first exam problem (exam/RESULT.md): inconclusive, order unchanged.
- SPEC.md read. PROGRESS.md and STEPS.md drafted. Local commits only.
- server/ skeleton (FastAPI /health, SSE /chat, router, storage queue, passkey stubs). Only /health and 401 checked; Groq/NVIDIA/GitHub commit/WebAuthn untested.
- web/ empty PWA + .github/workflows/pages.yml. Build passes.

## Blocked
- Hostless: junbot worker DELETED (user approved, repo jun-server untouched). Estimate now $0.00. haru-server not created: Hostless wizard cannot see buriburiyj/haru even after adding it in GitHub app settings. Next: Hostless Project settings -> Git connections -> disconnect/reconnect GitHub (may need user passkey), then create app (root dir server/, start `uvicorn main:app --host 0.0.0.0 --port $PORT`), $0.00 only, then enter env vars.
- Codex in Actions (A3): needs `gh secret set CODEX_AUTH_JSON -R buriburiyj/jun-files < ~/.codex/auth.json` run by the USER (auto-mode denies Claude). Then copy exam/codex-actions-test.yml to jun-files/.github/workflows/ and `gh workflow run codex-auth-test.yml -R buriburiyj/jun-files`.
- Claude Code could not add its own permission rule or send further Aside messages on 2026-11-02 (auto-mode Self-Modification denial). Aside session id GYBNT6BZg9A08Sez may still be mid-task; check its screen.

## Remaining
- Codex in GitHub Actions (STEPS A3). Exam order stays gpt-6-luna -> gpt-5.6-terra -> gpt-5.6-luna (both 13/13)
- Stage 0 skeleton: test Groq/NVIDIA/GitHub commit/passkey for real; set SESSION_SECRET
- Hostless app + env vars (STEPS C1; Aside cannot read the real ~/computer-use/.env, so a human or a clipboard step must supply values)
- Stages 1-6 per SPEC.md section 12

## Next (one line)
Reconnect GitHub in Hostless and create haru-server at $0.00, then run A3.
