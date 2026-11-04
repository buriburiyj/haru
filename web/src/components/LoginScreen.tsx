import { useRef, useState } from "react";
import Logo from "./Logo";
import { Button, Input } from "./ui";
import { isRegisteredDevice, loginErrorText, markRegisteredDevice, type LoginError } from "./auth/loginErrors";

export default function LoginScreen(props: {
  /** a ready message, or a kind ({kind: "network" | "token" | "cancelled" | "server"}) */
  error: string | LoginError;
  onSignIn: () => void | Promise<void>;
  onRegister: (setupToken: string) => void | Promise<void>;
}) {
  const registered = isRegisteredDevice();
  const [showRegister, setShowRegister] = useState(!registered);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  // The parent reports failure only through the `error` prop, so keep the latest value to read after the call.
  const errorRef = useRef(props.error);
  errorRef.current = props.error;

  const run = async (fn: () => void | Promise<void>) => {
    setBusy(true);
    try {
      await fn();
      await new Promise((r) => setTimeout(r, 0)); // let the parent render a failure first
      const failed = errorRef.current !== "" && errorRef.current !== undefined;
      if (!failed) markRegisteredDevice(); // success: this device has a passkey now
    } finally {
      setBusy(false);
    }
  };

  const message = props.error ? loginErrorText(props.error) : "";

  return (
    <main className="flex h-full flex-col items-center justify-center gap-4 px-4">
      <Logo size={64} />
      <p className="text-xl">패스키로 로그인하세요</p>
      <Button variant="primary" disabled={busy} onClick={() => run(props.onSignIn)}>
        로그인
      </Button>

      {!showRegister ? (
        <Button variant="ghost" onClick={() => setShowRegister(true)} className="text-muted underline">
          다른 기기 등록
        </Button>
      ) : (
        <div className="flex w-full max-w-sm flex-col items-center gap-3">
          <Input
            type="password"
            placeholder="설정 토큰 (처음 등록할 때만)"
            aria-label="설정 토큰"
            autoComplete="off"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <Button disabled={busy} onClick={() => run(() => props.onRegister(token))}>
            이 기기 등록
          </Button>
        </div>
      )}

      {message && (
        <p className="max-w-sm text-center text-sm text-danger" role="alert">
          {message}
        </p>
      )}
    </main>
  );
}
