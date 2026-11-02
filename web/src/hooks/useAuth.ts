import { useEffect, useState } from "react";
import { hasSession, login, register } from "../api";

// Logic moved unchanged from the former App.tsx (passkey login / register).
export function useAuth() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    hasSession().then(setAuthed);
  }, []);

  const run = async (fn: () => Promise<void>) => {
    setError("");
    try {
      await fn();
      setAuthed(true);
    } catch {
      setError("인증에 실패했어요. 다시 시도해 주세요.");
    }
  };

  return {
    authed,
    error,
    setAuthed,
    signIn: () => run(login),
    registerDevice: (setupToken: string) => run(() => register(setupToken)),
  };
}
