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

- Work placeholders (`{role:"assistant", content:"", kind:"task", taskId}`) in `messages` are kept when the chat is saved again. The model gets one short line ("(작업을 실행했습니다. 진행 내용은 별도 화면에 있습니다.)") instead of an empty assistant message.

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
- `GET /chats?q=&limit=&project_id=` -> `{chats:[{id,title,created,updated,preview,mode,task_ids}]}` newest first; `q` matches title and preview. Work conversations have `mode:"work"`; `task_ids` lets the client reopen their tasks. If the backing repository cannot be reached, it returns `200 {chats:[],warning:"storage_unavailable"}` and logs only the exception class/status.
- `GET /chats/{id}` -> `{id,title,messages,mode,task_ids}` (404 if missing). Messages may hold `images` ids and `model`; a Work placeholder is an empty assistant message such as `{"role":"assistant","content":"","kind":"task","taskId":"t-1"}`.
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
- Development mode is enabled only by `HARU_DEV=1`. It adds the two Vite localhost origins and accepts `Authorization: Bearer <HARU_DEV_TOKEN>` only when the ASGI server address is loopback. With `HARU_DEV` unset, CORS and auth keep the production configuration. `scripts/dev.sh` generates the short-lived token and writes it only to the ignored `web/.env.local` as `VITE_DEV_TOKEN`.
- `POST /tasks` `{content, mode, conversation_id?}` creates a queued Work task and returns `{id,status,chatId}`. If `conversation_id` is omitted, the server creates a conversation titled from the shortened request. It stores the user message followed by a task placeholder and returns the same `chatId` in the first `task` event. Existing conversations receive the same two messages. The pair is saved in one chat/index commit; if storage cannot be read, the message delta is queued for append on retry.
- Task API `mode` is still the permission mode: `always_ask` (ask), `auto_edit` (auto-edit), `plan`, `auto` (default), `skip` (quiet), `allow_all` (all). Local execution of `allow_all` is denied. Unknown commands are skipped; large deletion, external send/push/deploy, payment, and `.env` reads are blocked in every mode.
- `GET /tasks?active=true` lists active tasks with `computer`, `started_at`, `elapsed`, and `last_event_id`. `GET /tasks/{id}/events?after=N` replays events with IDs greater than `N`; `Last-Event-ID: N` is also accepted. Event IDs increase per task and reconnecting after a refresh does not replay earlier events.
- `GET /tasks/{id}` returns task metadata and the full stored event history, including terminal `done`, `failed`, or `stopped` events: `{"id":"t-1","content":"...","conversation_id":"chat-1","status":"done","last_event_id":9,"events":[{"id":1,"event":"task","data":{},"time":1794042000.0}]}`.
- Event stream uses the names below; every event's JSON `data` has the shown shape. A normal completion is `task`, `todos`, `status`, `action`, `checkpoint`, `action`, `output`, `summary`, `todos`, `done` (optional events are omitted when not applicable).

| Event | Example JSON data |
|---|---|
| `task` | `{"id":"t-1","content":"현재 폴더 파일 목록을 보고 README 첫 줄을 요약해줘","mode":"auto","conversation_id":"chat-1","chatId":"chat-1","chat_mode":"work","status":"queued"}` |
| `todos` | `{"todos":[{"id":"t1","text":"파일 목록 확인","done":false},{"id":"t2","text":"README 첫 줄 읽기","done":false},{"id":"t3","text":"한 문장으로 요약","done":false}]}` |
| `status` | `{"status":"running","worker":"mac","computer":"mac","started_at":1794042000.0,"elapsed":3,"resume_after":0}` |
| `action` | `{"id":"act-1","label":"파일 목록 확인 및 README 첫 줄 읽기","command":"ls -la && head -n 1 README.md","status":"running","outward":false}` |
| `checkpoint` | `{"action_id":"act-1","step":0,"command":"ls -la && head -n 1 README.md","output":"README.md\\n# Haru","commit":"abc123"}` |
| `output` | `{"id":"act-1","command":"ls -la && head -n 1 README.md","text":"README.md\\n# Haru","is_diff":false}` |
| `permission_required` | `{"id":"act-2","action_id":"act-2","title":"폴더를 만들까요?","kind":"other","command":"mkdir reports"}` |
| `permission` | `{"decision":"allow","task_id":"t-1"}` |
| `interjection` | `{"id":"ix-1","content":"다른 README도 확인해줘","status":"queued"}` |
| `interjection_applied` | `{"id":"ix-1","status":"queued_for_next_action"}` |
| `skipped` | `{"id":"act-3","command":"rm -rf build","reason":"항상 중지 대상 또는 .env 접근"}` |
| `error` | `{"id":"act-4","command":"head README.md","reason":"command failed","exit_code":1,"output":"파일을 찾을 수 없습니다"}` |
| `summary` | `{"text":"README 첫 줄은 Haru 프로젝트 제목입니다.","files":[{"path":"README.md","change":"modified"}],"skipped":[],"usage":[{"label":"Actions","value":"0분"}]}` |
| `done` | `{"result":"README 첫 줄은 Haru 프로젝트 제목입니다.","error":""}` |
| `failed` | `{"result":"","error":"model unavailable"}` |
| `stopped` | `{"id":"t-1","status":"stopped"}` |
| `mode_changed` | `{"mode":"always_ask"}` |
| `rewind_requested` | `{"id":"act-1","checkpoint":{"action_id":"act-1","commit":"abc123"}}` |
| `rewound` | `{"id":"act-1","checkpoint":"abc123"}` |

- `action.id`는 대응하는 `output.id`, `skipped.id`, `error.id`와 같습니다. `action.label`은 화면에 보이는 이름입니다. `kind`는 서버가 `delete|send|pay|other` 중에서 분류합니다. 외부 전송이 허용된 미래 이벤트는 `action.outward:true`로 표시합니다. 현재 외부 전송은 차단됩니다.
- `output.is_diff`는 출력에 Git diff 형식이 포함되면 `true`입니다. `summary.files`의 형식은 `{path,change:"added"|"modified"|"deleted"}`이고 `usage`는 `{label,value}[]`입니다. 현재 로컬 워커는 무료 한도 값을 산출하지 않아 빈 배열을 보낼 수 있습니다.
- `POST /tasks/{id}/rewind` `{action_id?}`는 마지막 worker 체크포인트로 되돌리기를 큐에 넣습니다. 완료 상태 task도 `rewind_requested` 후 queued 상태로 바꾸어 worker가 처리하고 `rewound`를 보냅니다. 대응 행동에 `outward:true`가 있으면 `{ok:false,can_rewind:false,reason:"외부로 보낸 행동은 되돌릴 수 없습니다"}`를 반환합니다.
- `POST /tasks/{id}/mode` `{mode}`는 실행 중 허락 모드를 바꾸고 `mode_changed`를 보냅니다. `allow_all`은 `actions`와 `codespaces` 컴퓨터에서만 허용됩니다.
- `POST /tasks/{id}/permission` `{decision:"allow"|"always"|"deny"}`, `POST /tasks/{id}/stop`, and `POST /tasks/{id}/message` `{content}` control a task.
- Workers authenticate with `X-Worker-Token` and `WORKER_TOKEN`: `POST /worker/claim` `{worker_id}`, `POST /worker/plan` `{task_id,entries}` -> `{label,command,summary,todos,model}`, `POST /worker/heartbeat` `{task_id,worker_id,checkpoint}`, `GET /worker/events?task_id=...` -> `{messages,permission,controls,mode,rewind_only,stopped}`, `POST /worker/permission` `{task_id,action_id,label,command}`, `POST /worker/event` `{task_id,event,data}`, and `POST /worker/done` `{task_id,result?,error?}`. The router suggests 3–6 short checklist items; if planning is unavailable, the initial single-prompt checklist remains. A worker lease expires after 120 seconds without heartbeat; the last checkpoint is returned on reassignment.
- `POST /telegram/webhook` validates `X-Telegram-Bot-Api-Secret-Token` against `TELEGRAM_WEBHOOK_SECRET` and only accepts the configured `TELEGRAM_CHAT_ID`. Configure `HARU_BOT_TOKEN` for notifications; webhook registration is intentionally a separate owner action.
