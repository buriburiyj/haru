# server/ hand-off (window B -> Codex)

Written 2026-11-04. Read `API.md` first (request/response shapes), then this file.

## State: everything below is done, tested and pushed
| Area | Files | Notes |
|---|---|---|
| Auth (passkey, Bearer token, signed challenge ids) | `main.py` | No cookies. Credentials live in jun-files `.agent/credentials.json` (public keys only). |
| Chat + SSE (`delta`, `notice`, `done`) | `main.py`, `router.py` | Groq easy / Codex hard / NVIDIA fallback. 429: wait once (<=6 s), then next model. |
| Chat storage (one commit per answer: chat file + `index.json`) | `storage.py` | Git Data API, serialized by a lock; failed commits are queued in `/tmp/queue`. |
| Codex through GitHub Actions | `codex.py`, `workflows/codex-chat.yml` | Measured live: ~34 s, 1 Actions minute. Monthly guard 1500 min. |
| Web search (DuckDuckGo, free) | `search.py` | Time-sensitive questions only (`web:"auto"`). |
| Photos + vision model | `uploads.py` | Raw-bytes upload, 3 MB, originals in `.agent/uploads/`. |
| Memory (+ automatic suggestions) | `memory.py` | Suggestions need a Groq call; gated by a cheap regex first. |
| Models list, usage counters | `router.py`, `usage.py` | `GET /models`, `GET /usage` (no billing fields). |
| GitHub connector (read only) | `connector.py` | Secret-looking files are never read. No write functions exist. |
| Projects | `projects.py` | `.agent/projects/`, files injected into the prompt (30,000 chars cap). |
| Artifacts | `artifacts.py` | `.agent/artifacts/`, saved after each answer, deduplicated. |
| Auto titles | `llm.py` | Groq, new chats only, falls back to the first words. |
| `effort` (low/medium/high) | `codex.py`, `router.py`, `main.py` | Passed to Codex as `-c model_reasoning_effort=...`; ignored by Groq/NVIDIA. |

## Tests
```
cd server
python -m venv .venv && .venv/bin/pip install fastapi uvicorn httpx webauthn pyyaml
.venv/bin/python -m unittest discover -s tests      # 99 tests, ~4 s, no network
```
`tests/test_memory_budget.py` runs the app in a fresh process with big requests and fails above 150 MB (currently ~97 MB).
Tests set `HARU_DISABLE_LLM=1`; features that call Groq are tested with `llm.ask` replaced.

## Not verified live (be careful)
- `effort`: the workflow change (`-c model_reasoning_effort="high"`) is only unit-tested. `server/workflows/codex-chat.yml` must be copied to jun-files `.github/workflows/` again before it takes effect; an old copy simply ignores `effort`. Run one real hard question with `effort:"high"` and read the Actions log if Codex rejects the flag (CLI versions differ).
- Two Hostless processes would each keep their own in-memory caches (chat index, memory, projects, artifacts) and could overwrite each other's `index.json`. The app is meant to run as one instance.

## Known gaps / next steps
1. **web wiring** (`web/src/api.ts`, owned with window A): `chat()` does not send `project_id` yet and does not surface `done.project_id` / `done.artifacts` (type `ChatDoneExtras` exists but is unused). `ChatOptions` has `effort`; add `project_id` the same way.
2. Codex has no real streaming: the answer arrives after the run finishes, in ~400-char chunks.
3. Groq/NVIDIA usage counters are in memory + `/tmp/haru_usage.json`; a redeploy can reset them early.
4. GitHub connector is read only on purpose. Write/delete/commit must wait for the permission-card UI.
5. Delete endpoints (chats, memory, projects, project files, artifacts) must only be called after a confirmation in the UI.
6. Free tiers: Groq/NVIDIA 429s are retried once; NVIDIA models sometimes answer 503 or hang (deepseek-v4.1-flash); the fallback chain handles it but slowly.

## Rules that still apply
- Never print, log or commit secrets. Only env **names** are listed in `API.md`.
- Hostless deploys are done with the `hostless` CLI (`hostless deploy --app haru-server --commit <sha> --wait`, once per push of `server/`); env vars are only listed by name (`hostless env list`), never revealed or set by an agent.
- Do not add dependencies without asking (the server uses only fastapi, uvicorn, httpx, webauthn).
- Keep server memory under 150 MB.
