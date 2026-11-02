import { useState } from "react";
import Logo from "./Logo";

export default function LoginScreen(props: {
  error: string;
  onSignIn: () => void;
  onRegister: (setupToken: string) => void;
}) {
  const [token, setToken] = useState("");
  return (
    <main className="flex h-full flex-col items-center justify-center gap-4 px-4">
      <Logo size={48} />
      <p className="text-xl">패스키로 로그인하세요</p>
      <button className="rounded-xl bg-accent px-5 py-2 text-accent-fg" onClick={props.onSignIn}>
        로그인
      </button>
      <input
        className="w-full max-w-sm rounded-xl border border-line bg-surface px-4 py-2"
        type="password"
        placeholder="설정 토큰 (처음 등록할 때만)"
        aria-label="설정 토큰"
        value={token}
        onChange={(e) => setToken(e.target.value)}
      />
      <button
        className="rounded-xl border border-line px-5 py-2"
        onClick={() => props.onRegister(token)}
      >
        이 기기 등록
      </button>
      {props.error && (
        <p className="text-sm text-danger" role="alert">
          {props.error}
        </p>
      )}
    </main>
  );
}
