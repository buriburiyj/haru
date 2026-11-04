const API = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

// ---- API types (server contract; see server/main.py) ----

/** One chat message. `model` is set by the server on assistant messages (id of the model that answered). */
export type Msg = {
  role: "user" | "assistant";
  content: string;
  model?: string;
  /** Upload ids from uploadImage() (user messages only; the server reads at most 3 per request). */
  images?: string[];
};

/** "auto" lets the server pick; "easy"/"hard" force the level; otherwise a model id from GET /models. */
export type ChatMode = "auto" | "easy" | "hard" | (string & {});

/** POST /chat body. Send the full history; the server saves one commit per answer. */
export type ChatRequest = {
  messages: Msg[];
  chat_id?: string;
  mode?: ChatMode;
  /** "auto" searches the web when the question is time-sensitive (default). */
  web?: "auto" | "on" | "off";
  /** Temporary chat: not saved, memory neither read nor written. */
  temporary?: boolean;
};

export type ChatOptions = { web?: ChatRequest["web"]; temporary?: boolean };

/** A source shown under an answer (web search result or GitHub file). */
export type Source = { title: string; url: string };

/** SSE events of POST /chat, in order: delta*, (notice)?, done. */
export type ChatEvent =
  | { kind: "delta"; text: string } // answer text chunk
  | { kind: "notice"; text: string } // user-facing status, e.g. "All models unavailable"
  | {
      kind: "done";
      chatId: string;
      saved: boolean; // false for temporary chats, when nothing answered, or while a GitHub save is queued
      model: string | null;
      title: string | null;
      temporary: boolean;
      sources: Source[];
    };

/** Entry of GET /chats (newest first). `created`/`updated` are unix seconds. */
export type ChatMeta = { id: string; title: string; created: number; updated: number; preview: string };

/** GET /chats/{id} */
export type ChatDetail = { id: string; title: string; messages: Msg[] };

/** Entry of GET /models. */
export type ModelInfo = { id: string; label: string; provider: "auto" | "groq" | "codex" | "nvidia" };
export type ModelList = { default: "auto"; models: ModelInfo[] };

/** Thrown for non-2xx responses. The message is "http <status>" (login errors are classified from it). */
export class HttpError extends Error {
  constructor(public status: number) {
    super(`http ${status}`);
  }
}

const b64uToBuf = (s: string): ArrayBuffer => {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + pad);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0)).buffer;
};
const bufToB64u = (b: ArrayBuffer | null): string | null => {
  if (!b) return null;
  let s = "";
  new Uint8Array(b).forEach((x) => (s += String.fromCharCode(x)));
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};

const TOKEN_KEY = "haru_token";

function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function setToken(t: string) {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: session lasts until reload via memory below */
  }
}

function authHeader(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function post(path: string, body?: unknown, headers: Record<string, string> = {}) {
  return fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader(), ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function takeToken(r: Response) {
  const d = await r.json().catch(() => ({}));
  if (!d.token) throw new Error("no token");
  setToken(d.token);
}

export function logout() {
  setToken("");
}

/** True if the session cookie is valid. */
export async function hasSession(): Promise<boolean> {
  try {
    const r = await fetch(`${API}/auth/me`, { headers: authHeader() });
    if (r.status === 401) setToken("");
    return r.ok;
  } catch {
    return false;
  }
}

export async function login(): Promise<void> {
  const ro = await post("/auth/login/options");
  if (!ro.ok) throw new HttpError(ro.status);
  const o = await ro.json();
  o.challenge = b64uToBuf(o.challenge);
  (o.allowCredentials ?? []).forEach((c: any) => (c.id = b64uToBuf(c.id)));
  const challengeId: string = o.challenge_id;
  delete o.challenge_id;
  const cred = (await navigator.credentials.get({ publicKey: o })) as PublicKeyCredential;
  const res = cred.response as AuthenticatorAssertionResponse;
  const r = await post("/auth/login/verify", {
    id: cred.id,
    rawId: bufToB64u(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bufToB64u(res.clientDataJSON),
      authenticatorData: bufToB64u(res.authenticatorData),
      signature: bufToB64u(res.signature),
      userHandle: bufToB64u(res.userHandle),
    },
  }, { "X-Challenge-Id": challengeId });
  if (!r.ok) throw new HttpError(r.status);
  await takeToken(r);
}

export async function register(setupToken: string): Promise<void> {
  const h: Record<string, string> = setupToken ? { "x-setup-token": setupToken } : {};
  const ro = await post("/auth/register/options", undefined, h);
  if (!ro.ok) throw new HttpError(ro.status);
  const o = await ro.json();
  o.challenge = b64uToBuf(o.challenge);
  o.user.id = b64uToBuf(o.user.id);
  (o.excludeCredentials ?? []).forEach((c: any) => (c.id = b64uToBuf(c.id)));
  const challengeId: string = o.challenge_id;
  delete o.challenge_id;
  const cred = (await navigator.credentials.create({ publicKey: o })) as PublicKeyCredential;
  const res = cred.response as AuthenticatorAttestationResponse;
  const r = await post(
    "/auth/register/verify",
    {
      id: cred.id,
      rawId: bufToB64u(cred.rawId),
      type: cred.type,
      response: {
        clientDataJSON: bufToB64u(res.clientDataJSON),
        attestationObject: bufToB64u(res.attestationObject),
      },
    },
    { ...h, "X-Challenge-Id": challengeId },
  );
  if (!r.ok) throw new HttpError(r.status);
  await takeToken(r);
}

/** POST /chat and yield parsed SSE events. Throws "unauthorized" on 401. */
export async function* chat(
  messages: Msg[],
  chatId?: string,
  mode: ChatMode = "auto",
  opts: ChatOptions = {},
): AsyncGenerator<ChatEvent> {
  const body: ChatRequest = { messages, chat_id: chatId, mode, ...opts };
  const r = await post("/chat", body);
  if (r.status === 401) {
    setToken("");
    throw new Error("unauthorized");
  }
  if (!r.ok || !r.body) throw new HttpError(r.status);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const ev = /^event: (.*)$/m.exec(block)?.[1];
      const data = /^data: (.*)$/m.exec(block)?.[1];
      if (!ev || data === undefined) continue;
      const parsed = JSON.parse(data);
      if (ev === "done") {
        yield {
          kind: "done",
          chatId: parsed.chat_id,
          saved: parsed.saved,
          model: parsed.model ?? null,
          title: parsed.title ?? null,
          temporary: !!parsed.temporary,
          sources: parsed.sources ?? [],
        };
      } else if (ev === "delta") {
        yield { kind: "delta", text: parsed as string };
      } else if (ev === "notice") {
        yield { kind: "notice", text: parsed as string };
      }
    }
  }
}

// ---- chat list / models (all need a session; 401 clears the stored token) ----

async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method,
    headers: { ...(body === undefined ? {} : { "Content-Type": "application/json" }), ...authHeader() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (r.status === 401) {
    setToken("");
    throw new Error("unauthorized");
  }
  if (!r.ok) throw new HttpError(r.status);
  return r.json() as Promise<T>;
}

/** GET /chats?q= — newest first; `q` matches title and preview. */
export const listChats = (q = "") =>
  api<{ chats: ChatMeta[] }>("GET", `/chats${q ? `?q=${encodeURIComponent(q)}` : ""}`).then((d) => d.chats);
/** GET /chats/{id} — HttpError(404) if missing. */
export const getChat = (id: string) => api<ChatDetail>("GET", `/chats/${encodeURIComponent(id)}`);
/** POST /chats/{id}/rename */
export const renameChat = (id: string, title: string) =>
  api<{ ok: true }>("POST", `/chats/${encodeURIComponent(id)}/rename`, { title });
/** DELETE /chats/{id} — call only after the user confirmed in the UI. */
export const deleteChat = (id: string) => api<{ ok: true }>("DELETE", `/chats/${encodeURIComponent(id)}`);
/** GET /models */
export const getModels = () => api<ModelList>("GET", "/models");

// ---- usage (settings > usage). Times are unix seconds (UTC). No billing fields. ----

export type UsageInfo = {
  as_of: number;
  /** Null when GitHub could not be reached. */
  codex: { minutes_used: number; minutes_limit: number; runs: number; resets_at: number } | null;
  groq: ProviderUsage;
  nvidia: ProviderUsage;
};
export type ProviderUsage = { calls_today: number; rate_limited_today: number; resets_at: number };

/** GET /usage */
export const getUsage = () => api<UsageInfo>("GET", "/usage");

// ---- photos ----

export type UploadInfo = { id: string; name: string; mime: string; size: number };

/** POST /uploads with the raw bytes (jpeg, png, webp, gif; max 3 MB). Put the returned id in Msg.images. */
export async function uploadImage(file: Blob, name = ""): Promise<UploadInfo> {
  const r = await fetch(`${API}/uploads?name=${encodeURIComponent(name)}`, {
    method: "POST",
    headers: { "Content-Type": file.type || "application/octet-stream", ...authHeader() },
    body: file,
  });
  if (r.status === 401) {
    setToken("");
    throw new Error("unauthorized");
  }
  if (!r.ok) throw new HttpError(r.status); // 413 too large, 415 not an image, 502 storage down
  return r.json();
}

/** GET /uploads/{id} as a blob URL for <img src>. Revoke it with URL.revokeObjectURL when done. */
export async function getUploadUrl(id: string): Promise<string> {
  const r = await fetch(`${API}/uploads/${encodeURIComponent(id)}`, { headers: authHeader() });
  if (!r.ok) throw new HttpError(r.status);
  return URL.createObjectURL(await r.blob());
}

// ---- memory (topic memories) ----

export type MemoryEntry = { id: string; topic: string; content: string; created: number; updated: number };

/** GET /memory (newest first) */
export const listMemory = () => api<{ memories: MemoryEntry[] }>("GET", "/memory").then((d) => d.memories);
/** POST /memory — 400 invalid, 409 full */
export const createMemory = (topic: string, content: string) => api<MemoryEntry>("POST", "/memory", { topic, content });
/** PUT /memory/{id} */
export const updateMemory = (id: string, patch: { topic?: string; content?: string }) =>
  api<MemoryEntry>("PUT", `/memory/${encodeURIComponent(id)}`, patch);
/** DELETE /memory/{id} — call only after the user confirmed in the UI. */
export const deleteMemory = (id: string) => api<{ ok: true }>("DELETE", `/memory/${encodeURIComponent(id)}`);

// ---- GitHub connector (read only) ----

export type GithubRepo = { name: string; full_name: string; private: boolean; description: string; url: string; default_branch: string };
export type GithubEntry = { name: string; path: string; type: "file" | "dir"; size: number };
export type GithubFile = { repo: string; path: string; size: number; text: string; truncated: boolean; url: string };

/** GET /github/repos */
export const githubRepos = () => api<{ repos: GithubRepo[] }>("GET", "/github/repos").then((d) => d.repos);
/** GET /github/files — folders first. Errors: 400 bad path, 404 not accessible. */
export const githubFiles = (repo: string, path = "") =>
  api<{ files: GithubEntry[] }>("GET", `/github/files?repo=${encodeURIComponent(repo)}&path=${encodeURIComponent(path)}`).then((d) => d.files);
/** GET /github/file — text files up to 200 KB; 403 for secret-looking files, 413 too large, 415 binary. */
export const githubFile = (repo: string, path: string) =>
  api<GithubFile>("GET", `/github/file?repo=${encodeURIComponent(repo)}&path=${encodeURIComponent(path)}`);
