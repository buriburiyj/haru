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
  temporary?: boolean,                                        // default false
  project_id?: string,                                        // chat inside a project (see Projects); a chat keeps its project
  effort?: "low"|"medium"|"high" }                            // reasoning effort, used by Codex only; Groq and NVIDIA ignore it
```
- `images` (user messages only, max 3 used per request) are ids returned by `POST /uploads`. With images the server uses the vision model and ignores `mode`.
- `temporary: true`: nothing is saved (no chat, no artifacts) and memory is neither read, written nor suggested.
- Project chats: the project's instructions and files are given to the model in every message. If `project_id` is missing but the chat already belongs to a project, that project is used. A deleted project is ignored.
- Easy questions never start GitHub Actions. Hard questions go to Codex (gpt-6-luna, gpt-5.6-terra, gpt-5.6-luna, tried in one Actions run), then NVIDIA.

Response: `text/event-stream`. Events (shapes unchanged):
- `delta` data `"text chunk"`; Codex answers arrive in a few big chunks (about 400 chars each) after a wait.
- `notice` data `"status text"` (Korean, user-facing): search started, reading photo, checking GitHub, Codex preparing (about 30-60 s, then every 15 s while working), Codex unavailable, memory saved, rate limit wait ("요청이 몰려서 잠시 기다린 뒤 다시 시도해요." = one retry after 1-6 s; then "요청이 많아서 다른 모델로 답해요."), all models unavailable. Show as a status line, not as answer text.
- `done` data `{chat_id, saved, model, title, temporary, project_id, artifacts, sources}`
  - `model`: id of the model that answered (null if none). `title`: chat title (null if not saved). For a new chat the title is a short Groq-made title (same language as the question); it falls back to the first words of the question, and a renamed chat keeps its name.
  - `project_id`: project used for this chat (null if none). `artifacts`: `[{id,title,language}]` saved from this answer (see Artifacts).
  - A `notice` "기억 업데이트됨" arrives right before `done` when the server saved or updated a memory from the conversation (see Memory).
  - `saved`: false means not saved (temporary, no answer, or GitHub failed and it is queued for retry).
  - `sources`: `[{title,url}]` for web search results and GitHub files that were used (empty array otherwise). Web search sources are also appended to the answer text as a `출처` markdown list.

Real Codex timing (measured once on the live server): first notice at 5 s, answer after about 34 s, 1 Actions minute used, answered by gpt-6-luna.

If a question names a repo and asks about its files (`jun-files에 뭐 있어?`, `jun-files의 README.md 읽어줘`), the server reads it from GitHub (read only) and gives it to the model. Photos in the same message skip this.

## Chats
- `GET /chats?q=&limit=&project_id=` -> `{chats:[{id,title,created,updated,preview}]}` newest first; `q` matches title and preview.
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

## Projects (instructions + text files given to the model in every chat of the project)
Project: `{id, name, instructions, files:[{name,content}], created, updated}`. Limits: name 60 chars, instructions 4000, 10 files, 20,000 chars per file, 100,000 in total (`413`), file names without slashes. Max 50 projects (`409`). Stored in `.agent/projects/`.
- `GET /projects` -> `{projects:[{id,name,instructions_preview,files:[names],created,updated}]}` newest first
- `POST /projects` `{name, instructions?, files?}` -> project. `400` invalid, `413` too big.
- `GET /projects/{id}` -> project or `404`
- `PUT /projects/{id}` `{name?, instructions?, files?}` -> project (`files`, if sent, replaces the whole list)
- `POST /projects/{id}/files` `{name, content}` -> project (adds, or replaces the file with the same name)
- `DELETE /projects/{id}/files/{name}` -> project. Call only after the user confirmed.
- `DELETE /projects/{id}` -> `{ok:true}`. Call only after the user confirmed. The project's chats are kept.
- `GET /chats?project_id=<id>` lists the chats of one project.

## Artifacts (code/HTML blocks from answers)
After a (non-temporary) answer the server saves its fenced code blocks in `.agent/artifacts/`: every `html` and `svg` block, and other languages (python, js, ts, css, ...) when they are at least 10 lines. Max 5 per answer; the same block in the same chat is stored once (regenerating does not duplicate).
Artifact: `{id, title, language, chat_id, created, size, content}`; the title comes from `<title>`/`<h1>` or the first comment line, else "<language> snippet".
- `GET /artifacts?chat_id=` -> `{artifacts:[{id,title,language,chat_id,created,size}]}` newest first (no content)
- `GET /artifacts/{id}` -> artifact with `content`, or `404`
- `DELETE /artifacts/{id}` -> `{ok:true}`. Call only after the user confirmed.
- The ids of artifacts created by an answer are in `done.artifacts`.

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
- Automatic suggestions: after an answer, if the user's message talks about themself (name, job, diet, tools, habits, preferences), a short Groq call decides whether to remember it. A new topic is added, an existing topic (same name, any case) is updated, and the notice `기억 업데이트됨` is sent before `done`. Passwords, keys, long numbers, health/payment details and other people's data are never saved. Never runs in temporary chats and never together with an explicit `기억해줘`.

## Environment variables (names only)
Required: `GROQ_API_KEY`, `NVIDIA_API_KEY`, `GITHUB_TOKEN`, `SESSION_SECRET`, `SETUP_TOKEN`.
Optional (defaults): `GROQ_MODEL` (openai/gpt-oss-20b), `GITHUB_OWNER` (buriburiyj), `GITHUB_REPO` (jun-files), `GITHUB_BRANCH` (main),
`CRED_FILE` (/tmp/credentials.json), `QUEUE_DIR` (/tmp/queue), `CRED_REMOTE_PATH` (.agent/credentials.json),
`UPLOAD_MAX_BYTES` (3145728), `USAGE_FILE` (/tmp/haru_usage.json), `HARU_DISABLE_LLM` (unset; set to 1 in tests to turn off the Groq helper calls for titles and memory suggestions), `CODEX_WORKFLOW` (codex-chat.yml), `CODEX_MONTHLY_MINUTES` (1500), `CODEX_TIMEOUT` (300), `CODEX_START_TIMEOUT` (90).

## Codex setup (one time, by the owner)
1. Copy `server/workflows/codex-chat.yml` to `jun-files/.github/workflows/codex-chat.yml` (secret `CODEX_AUTH_JSON` already exists there).
2. The `GITHUB_TOKEN` used by the server needs **Actions: Read and write** on jun-files (done; verified live). If it is missing, Codex is skipped for 10 minutes after a failed attempt and NVIDIA answers.

## Background tasks and worker
- `POST /tasks` `{content, mode, conversation_id}` creates a queued task. Modes: `always_ask` (매번 확인), `auto_edit` (허용된 로컬 파일 수정 자동), `plan` (계획만), `auto` (기본, 안전한 읽기 작업 자동·수정은 확인), `skip` (사전 허락 없는 행동 건너뜀), `allow_all` (Actions/Codespaces만; 로컬 워커에서는 실행 불가). 현재 워커는 분류된 읽기/일부 파일 명령만 실행하며, 분류되지 않은 명령은 건너뜁니다.
- `GET /tasks/{id}/events` streams named SSE events until completion. Order for a successful task is `task`, `status`, `action`, `output`, `summary`, `done` (and `checkpoint` events may appear between action/output):
```text
event: task
data: {"id":"abc123","content":"현재 폴더 파일 목록을 보고 README 첫 줄을 요약해줘","mode":"auto","conversation_id":"chat-1","status":"queued"}

event: action
data: {"command":"ls -la && head -n 1 README.md","model":"..."}

event: output
data: {"command":"ls -la && head -n 1 README.md","text":"README.md\\n# Haru"}

event: summary
data: {"text":"현재 폴더에는 README.md가 있고, 첫 줄은 Haru 프로젝트 제목입니다.","files":[]}

event: done
data: {"result":"현재 폴더에는 README.md가 있고, 첫 줄은 Haru 프로젝트 제목입니다.","error":""}
```
- `status`: `{status,worker,resume_after}`; `action`: `{command,model}`; `output`: `{command,text}`; `summary`: `{text,files}`; `checkpoint`: `{step,command,output,commit}`; `permission_required`: `{command}`; `skipped`: `{command?,reason}`; `error`: `{reason,exit_code?,output?}`. SSE `id` is a per-task increasing integer.
- `POST /tasks/{id}/permission` `{decision:"allow"|"always"|"deny"}`, `POST /tasks/{id}/stop`, and `POST /tasks/{id}/message` `{content}` control a task.
- Workers authenticate with `X-Worker-Token` and `WORKER_TOKEN`: `POST /worker/claim` `{worker_id}`, `POST /worker/plan` `{task_id,entries}`, `POST /worker/heartbeat` `{task_id,worker_id,checkpoint}`, `GET /worker/events?task_id=...`, `POST /worker/permission` `{task_id,command}`, `POST /worker/event` `{task_id,event,data}`, and `POST /worker/done` `{task_id,result?,error?}`. A worker lease expires after 120 seconds without heartbeat; the last checkpoint is returned on reassignment.
- `POST /telegram/webhook` validates `X-Telegram-Bot-Api-Secret-Token` against `TELEGRAM_WEBHOOK_SECRET` and only accepts the configured `TELEGRAM_CHAT_ID`. Configure `HARU_BOT_TOKEN` for notifications; webhook registration is intentionally a separate owner action.
