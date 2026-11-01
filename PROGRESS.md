# PROGRESS

Last updated: 2026-11-01 (Claude Code, deadline 2026-11-02)

## Done
- GitHub Pages live: https://buriburiyj.github.io/haru (200). Token haru-store (jun-files Contents rw, expires 2027-01-30) saved as HARU_GH_TOKEN in ~/computer-use/.env, verified with API 200.
- Repo buriburiyj/haru created and pushed. Box started; both models answered the first exam problem (exam/RESULT.md): inconclusive, order unchanged.
- SPEC.md read. PROGRESS.md and STEPS.md drafted. Local commits only.
- server/ skeleton (FastAPI /health, SSE /chat, router, storage queue, passkey stubs). Only /health and 401 checked; Groq/NVIDIA/GitHub commit/WebAuthn untested.
- web/ empty PWA + .github/workflows/pages.yml. Build passes.

## Blocked
- Hostless (C1): wizard showed est. $0.00-$0.47/mo with 'Free capacity left: 0 vCPU, 0 MB RAM' (junbot already uses the free quota). Stopped per rule 1; nothing created. Hostless also cannot see repo haru (only jun-server). Need a different free host for server/ - see STEPS.md C1.

## Remaining
- Stage 0 exam: harder problem with unit tests; Codex in GitHub Actions (STEPS A2, A3)
- Stage 0 skeleton: test Groq/NVIDIA/GitHub commit/passkey for real; set SESSION_SECRET
- Browser tasks for Aside (Hostless app, GitHub Pages, tokens) - see STEPS.md
- Stages 1-6 per SPEC.md section 12

## Next (one line)
Decide the free server host (C1 options), then A3 (Codex in Actions). A2 done: both 13/13, order unchanged.
