# Haru server API

Base URL: `https://haru-server.hostless.app`. All routes except `/health` and `/auth/*` need
`Authorization: Bearer <token>` (token comes from login/register; no cookies). Missing or bad token = `401`.
Errors are `{"detail": "..."}`. Storage problems are `502`. Types for the web app live in `web/src/api.ts`.

## Auth
| Route | Body | Response |
|---|---|---|
| `POST /auth/register/options` (header `X-Setup-Token`) | – | WebAuthn options + `challenge_id` |
| `POST /auth/register/verify` (headers `X-Setup-Token`, `X-Challenge-Id`) | credential JSON | `{ok, token}` |
| `POST /auth/login/options` | – | WebAuthn options + `challenge_id` |
| `POST /auth/login/verify` (header `X-Challenge-Id`) | credential JSON | `{ok, token}` |
| `GET /auth/me` | – | `{ok:true}` |

## Chat: `POST /chat`
Request:
```
{ messages: [{role:"user"|"assistant"|"system", content:string, images?:string[], model?:string}],
  chat_id?: string,
  mode?: "auto"|"easy"|"hard"|<model id from GET /models>,   // default "auto"
  web?: "auto"|"on"|"off",                                    // default "auto" (search when the question is time-sensitive)
  temporary?: boolean }                                       // default false
```
- `images` (user messages only, max 3 used per request) are ids returned by `POST /uploads`. With images the server uses the vision model and ignores `mode`.
- `temporary: true`: nothing is saved and memory is neither read nor written.
- Easy questions never start GitHub Actions. Hard questions go to Codex (gpt-6-luna, gpt-5.6-terra, gpt-5.6-luna, tried in one Actions run), then NVIDIA.

Response: `text/event-stream`. Events (shapes unchanged):
- `delta` data `"text chunk"`; Codex answers arrive in a few big chunks (about 400 chars each) after a wait.
- `notice` data `"status text"` (Korean, user-facing): search started, reading photo, checking GitHub, Codex preparing (about 30-60 s, then every 15 s while working), Codex unavailable, memory saved, rate limit wait ("요청이 몰려서 잠시 기다린 뒤 다시 시도해요." = one retry after 1-6 s; then "요청이 많아서 다른 모델로 답해요."), all models unavailable. Show as a status line, not as answer text.
- `done` data `{chat_id, saved, model, title, temporary, sources}`
  - `model`: id of the model that answered (null if none). `title`: chat title (null if not saved).
  - `saved`: false means not saved (temporary, no answer, or GitHub failed and it is queued for retry).
  - `sources`: `[{title,url}]` for web search results and GitHub files that were used (empty array otherwise). Web search sources are also appended to the answer text as a `출처` markdown list.

Real Codex timing (measured once on the live server): first notice at 5 s, answer after about 34 s, 1 Actions minute used, answered by gpt-6-luna.

If a question names a repo and asks about its files (`jun-files에 뭐 있어?`, `jun-files의 README.md 읽어줘`), the server reads it from GitHub (read only) and gives it to the model. Photos in the same message skip this.

## Chats
- `GET /chats?q=&limit=` -> `{chats:[{id,title,created,updated,preview}]}` newest first; `q` matches title and preview.
- `GET /chats/{id}` -> `{id,title,messages}` (404 if missing). Messages may hold `images` ids and `model`.
- `POST /chats/{id}/rename` `{title}` -> `{ok:true}`
- `DELETE /chats/{id}` -> `{ok:true}`. Call only after the user confirmed.

## Models: `GET /models`
`{default:"auto", models:[{id,label,provider}]}` where `provider` is `auto` (first entry, id `auto`, label 자동), `groq`, `codex`, or `nvidia`.
Order: auto, one Groq model, gpt-6-luna, gpt-5.6-terra, gpt-5.6-luna, three NVIDIA models. The vision model is internal and not listed.

## Uploads (photos)
- `POST /uploads?name=<file name>` with the raw image bytes as the body (`Content-Type: image/*`; no multipart). jpeg, png, webp, gif only, checked by content; max 3 MB.
  Response `{id,name,mime,size}`. `413` too large, `415` not an image, `502` storage down. Originals are stored in jun-files `.agent/uploads/`.
- `GET /uploads/{id}` -> image bytes (needs the Authorization header, so load it with fetch and use a blob URL). `404` if unknown.
- Then send the id in a user message: `{role:"user", content:"What is this?", images:[id]}`.

## Usage: `GET /usage`
```
{ as_of, codex: { minutes_used, minutes_limit, runs, resets_at } | null,
  groq:   { calls_today, rate_limited_today, resets_at },
  nvidia: { calls_today, rate_limited_today, resets_at } }
```
All times are unix seconds (UTC). Codex numbers are this month's GitHub Actions minutes (`minutes_limit` is our guard, default 1500 of the free 2000; `resets_at` = start of next month); `codex` is null if GitHub is unreachable. Groq/NVIDIA counts are requests made today (a 429 counts as a call and in `rate_limited_today`) and reset at 00:00 UTC. They live in server memory plus a file in /tmp, so a redeploy can reset them early. No billing fields.

## GitHub connector (read only)
Reads what the server's `GITHUB_TOKEN` can see. There is no write, delete or commit API.
- `GET /github/repos` -> `{repos:[{name,full_name,private,description,url,default_branch}]}`
- `GET /github/files?repo=<name or owner/name>&path=` -> `{repo,path,files:[{name,path,type:"file"|"dir",size}]}` (folders first, max 100). `400` bad path / that path is a file, `404` not accessible.
- `GET /github/file?repo=&path=` -> `{repo,path,size,text,truncated,url}` (text only, up to 200 KB, first 20,000 chars returned). `403` secret-looking file (`.env`, `*.pem`, `*.key`, names with `credentials` or `secret`), `413` too large, `415` binary.
- Writing, deleting and committing will only be added after the permission-card UI exists.

## Memory (topic memories in `.agent/memory/`)
Entry: `{id, topic, content, created, updated}` (topic max 60 chars, content max 2000, max 200 entries).
- `GET /memory` -> `{memories:[...]}` newest first. `GET /memory/{id}` -> entry or 404.
- `POST /memory` `{topic, content}` -> entry. `400` invalid, `409` full.
- `PUT /memory/{id}` `{topic?, content?}` -> entry.
- `DELETE /memory/{id}` -> `{ok:true}`. Call only after the user confirmed.
- In normal (non-temporary) chats the saved memories are given to the model automatically, and a message like `기억해줘: ...` or `remember that ...` saves a new memory (notice `기억했어요: ...`).

## Environment variables (names only)
Required: `GROQ_API_KEY`, `NVIDIA_API_KEY`, `GITHUB_TOKEN`, `SESSION_SECRET`, `SETUP_TOKEN`.
Optional (defaults): `GROQ_MODEL` (openai/gpt-oss-20b), `GITHUB_OWNER` (buriburiyj), `GITHUB_REPO` (jun-files), `GITHUB_BRANCH` (main),
`CRED_FILE` (/tmp/credentials.json), `QUEUE_DIR` (/tmp/queue), `CRED_REMOTE_PATH` (.agent/credentials.json),
`UPLOAD_MAX_BYTES` (3145728), `USAGE_FILE` (/tmp/haru_usage.json), `CODEX_WORKFLOW` (codex-chat.yml), `CODEX_MONTHLY_MINUTES` (1500), `CODEX_TIMEOUT` (300), `CODEX_START_TIMEOUT` (90).

## Codex setup (one time, by the owner)
1. Copy `server/workflows/codex-chat.yml` to `jun-files/.github/workflows/codex-chat.yml` (secret `CODEX_AUTH_JSON` already exists there).
2. The `GITHUB_TOKEN` used by the server needs **Actions: Read and write** on jun-files (done; verified live). If it is missing, Codex is skipped for 10 minutes after a failed attempt and NVIDIA answers.
