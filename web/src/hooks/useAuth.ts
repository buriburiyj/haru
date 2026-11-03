import { useEffect, useState } from "react";
import { hasSession, login, register } from "../api";
import { classifyLoginError, LoginError } from "../components/auth/loginErrors";

// Passkey login / register state. Failures are reported as a LoginError kind (network, token, cancelled, server).
export function useAuth() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [error, setError] = useState<string | LoginError>("");

  useEffect(() => {
    hasSession().then(setAuthed);
  }, []);

  const run = async (fn: () => Promise<void>, isRegister: boolean) => {
    setError("");
    try {
      await fn();
      setAuthed(true);
    } catch (err) {
      let kind = classifyLoginError(err);
      // A 401 on login means the passkey was not accepted, not a wrong setup token.
      if (!isRegister && kind === "token") kind = "server";
      setError({ kind });
    }
  };

  return {
    authed,
    error,
    setAuthed,
    signIn: () => run(login, false),
    registerDevice: (setupToken: string) => run(() => register(setupToken), true),
  };
}
