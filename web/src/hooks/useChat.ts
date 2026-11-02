import { useState } from "react";
import { chat, Msg } from "../api";

// SSE streaming logic moved unchanged from the former App.tsx send().
export function useChat(onUnauthorized: () => void) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [chatId, setChatId] = useState<string | undefined>();

  const send = async (text: string) => {
    const content = text.trim();
    if (!content || busy) return;
    const history: Msg[] = [...msgs, { role: "user", content }];
    setMsgs([...history, { role: "assistant", content: "" }]);
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
      if ((err as Error).message === "unauthorized") onUnauthorized();
      else setNotice("연결에 문제가 있어요.");
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setMsgs([]);
    setChatId(undefined);
    setNotice("");
  };

  return { msgs, busy, notice, chatId, send, reset };
}
