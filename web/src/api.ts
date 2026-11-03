const API = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export type Msg = { role: "user" | "assistant"; content: string };

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
  const o = await (await post("/auth/login/options")).json();
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
  if (!r.ok) throw new Error("login failed");
  await takeToken(r);
}

export async function register(setupToken: string): Promise<void> {
  const h: Record<string, string> = setupToken ? { "x-setup-token": setupToken } : {};
  const ro = await post("/auth/register/options", undefined, h);
  if (!ro.ok) throw new Error("register not allowed");
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
  if (!r.ok) throw new Error("register failed");
  await takeToken(r);
}

export type ChatEvent =
  | { kind: "delta"; text: string }
  | { kind: "notice"; text: string }
  | { kind: "done"; chatId: string; saved: boolean };

/** POST /chat and yield parsed SSE events. Throws "unauthorized" on 401. */
export async function* chat(messages: Msg[], chatId?: string): AsyncGenerator<ChatEvent> {
  const r = await post("/chat", { messages, chat_id: chatId });
  if (r.status === 401) {
    setToken("");
    throw new Error("unauthorized");
  }
  if (!r.ok || !r.body) throw new Error(`http ${r.status}`);
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
      const text = JSON.parse(data) as string;
      if (ev === "done") {
        const d = JSON.parse(text);
        yield { kind: "done", chatId: d.chat_id, saved: d.saved };
      } else if (ev === "delta") {
        yield { kind: "delta", text };
      } else if (ev === "notice") {
        yield { kind: "notice", text };
      }
    }
  }
}
