// Step-by-step login errors. The hook can pass either a ready message (string) or a kind.
export type LoginErrorKind = "network" | "token" | "cancelled" | "server";
export type LoginError = { kind: LoginErrorKind };

export const LOGIN_ERROR_TEXT: Record<LoginErrorKind, string> = {
  network: "서버에 연결하지 못했습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.",
  token: "설정 토큰이 맞지 않습니다. 다시 확인해 주세요.",
  cancelled: "패스키 확인을 취소했습니다. 다시 시도해 주세요.",
  server: "서버에 문제가 생겼습니다. 잠시 뒤에 다시 시도해 주세요.",
};

export function loginErrorText(e: string | LoginError): string {
  return typeof e === "string" ? e : LOGIN_ERROR_TEXT[e.kind];
}

/** Maps a thrown value from the passkey/register calls to a kind. Meant for the auth hook (not wired yet). */
export function classifyLoginError(err: unknown): LoginErrorKind {
  const name = (err as { name?: string } | null)?.name;
  const msg = (err as { message?: string } | null)?.message ?? "";
  if (name === "NotAllowedError" || name === "AbortError") return "cancelled";
  if (err instanceof TypeError || /failed to fetch|network/i.test(msg)) return "network";
  const code = /http (\d{3})/.exec(msg)?.[1];
  if (code === "401" || code === "403") return "token";
  return "server";
}

const KEY = "haru.registered";
export function isRegisteredDevice(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}
export function markRegisteredDevice() {
  try {
    localStorage.setItem(KEY, "1");
  } catch {
    /* ignore */
  }
}
