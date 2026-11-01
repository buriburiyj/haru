import { FormEvent, useEffect, useState } from "react";
import { chat, hasSession, login, register, Msg } from "./api";

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [setupToken, setSetupToken] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [chatId, setChatId] = useState<string | undefined>();

  useEffect(() => {
    hasSession().then(setAuthed);
  }, []);

  const auth = async (fn: () => Promise<void>) => {
    setError("");
    try {
      await fn();
      setAuthed(true);
    } catch {
      setError("인증에 실패했어요. 다시 시도해 주세요.");
    }
  };

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const content = text.trim();
    if (!content || busy) return;
    const history: Msg[] = [...msgs, { role: "user", content }];
    setMsgs([...history, { role: "assistant", content: "" }]);
    setText("");
    setNotice("");
    setBusy(true);
    try {
      for await (const ev of chat(history, chatId)) {
        if (ev.kind === "delta") {
          setMsgs((m) => {
            const last = m[m.length - 1];
            return [...m.slice(0, -1), { ...last, content: last.content + ev.text }];
          });
        } else if (ev.kind === "notice") {
          setNotice(ev.text);
        } else {
          setChatId(ev.chatId);
          if (!ev.saved) setNotice("저장이 지연되고 있어요. 나중에 다시 시도해요.");
        }
      }
    } catch (err) {
      if ((err as Error).message === "unauthorized") setAuthed(false);
      else setNotice("연결에 문제가 있어요.");
    } finally {
      setBusy(false);
    }
  };

  if (authed === null) return <main className="home" />;

  if (!authed) {
    return (
      <main className="home">
        <p className="greeting">패스키로 로그인하세요</p>
        <button className="btn" onClick={() => auth(login)}>로그인</button>
        <input className="prompt" type="password" placeholder="설정 토큰 (처음 등록할 때만)"
          value={setupToken} onChange={(e) => setSetupToken(e.target.value)} aria-label="설정 토큰" />
        <button className="btn" onClick={() => auth(() => register(setupToken))}>이 기기 등록</button>
        {error && <p className="notice" role="alert">{error}</p>}
      </main>
    );
  }

  return (
    <main className="home">
      {msgs.length === 0 && <p className="greeting">안녕하세요, 오늘 하루는 어떠세요?</p>}
      <div className="log">
        {msgs.map((m, i) => (
          <p key={i} className={`bubble ${m.role}`}>{m.content}</p>
        ))}
      </div>
      {notice && <p className="notice">{notice}</p>}
      <form onSubmit={send} className="form">
        <input className="prompt" type="text" aria-label="메시지 입력" value={text}
          onChange={(e) => setText(e.target.value)} disabled={busy} />
      </form>
    </main>
  );
}
