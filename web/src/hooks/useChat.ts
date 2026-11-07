import { useCallback, useRef, useState } from "react";
import { chat as chatApi, deleteChat, getChat, renameChat, type ChatDetail, type ChatMode, type Msg } from "../api";
import type { MsgMeta } from "../components/chat/dataTypes";
import { isTempChat, setTempChat } from "../components/temp/TempChat";

export type SendOptions = { mode: ChatMode; web: "auto" | "off"; images?: string[] };

/**
 * Chat state: messages (+ per-message meta), streaming over SSE, open / rename / delete.
 * Streaming logic is the same as before (delta / notice / done); the new parts use done.chatId, done.title, done.model, done.sources.
 * `onChanged` is called when the saved chat list changed (answer saved, renamed, deleted) so the list can reload.
 */
export function useChat(onUnauthorized: () => void, onChanged: () => void = () => {}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [metas, setMetas] = useState<(MsgMeta | undefined)[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [chatId, setChatId] = useState<string | undefined>();
  const [title, setTitle] = useState("");
  const busyRef = useRef(false);

  const send = useCallback(
    async (text: string, opts: SendOptions) => {
      const content = text.trim();
      const images = opts.images ?? [];
      if ((!content && images.length === 0) || busyRef.current) return;
      busyRef.current = true;
      const temporary = isTempChat();
      const userMsg: Msg = { role: "user", content, ...(images.length ? { images } : {}) };
      const history: Msg[] = [...msgs, userMsg];
      setMsgs([...history, { role: "assistant", content: "" }]);
      setMetas((m) => [...m, undefined, { auto: opts.mode === "auto" }]);
      setNotice("");
      setBusy(true);
      const setLastMeta = (patch: MsgMeta) =>
        setMetas((m) => [...m.slice(0, -1), { ...(m[m.length - 1] ?? {}), ...patch }]);
      try {
        for await (const ev of chatApi(history, temporary ? undefined : chatId, opts.mode, { web: opts.web, temporary })) {
          if (ev.kind === "delta") {
            setNotice("");
            setMsgs((m) => {
              const last = m[m.length - 1];
              return [...m.slice(0, -1), { ...last, content: last.content + ev.text }];
            });
          } else if (ev.kind === "notice") {
            setNotice(ev.text);
          } else {
            if (!ev.temporary) setChatId(ev.chatId);
            if (ev.title) setTitle(ev.title);
            setLastMeta({ model: ev.model ?? undefined, sources: ev.sources });
            setNotice(!ev.saved && !ev.temporary ? "저장이 지연되고 있어요. 나중에 다시 시도해요." : "");
            if (ev.saved) onChanged();
          }
        }
      } catch (err) {
        if ((err as Error).message === "unauthorized") onUnauthorized();
        else setNotice("연결에 문제가 있어요.");
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [msgs, chatId, onUnauthorized, onChanged],
  );

  const reset = useCallback(() => {
    setMsgs([]);
    setMetas([]);
    setChatId(undefined);
    setTitle("");
    setNotice("");
  }, []);

  /** Opens a saved chat (GET /chats/{id}). Leaves temporary mode. Returns the chat (with task_ids) or null when it could not be opened. */
  const open = useCallback(
    async (id: string): Promise<ChatDetail | null> => {
      try {
        const d = await getChat(id);
        setTempChat(false);
        setMsgs(d.messages);
        setMetas(d.messages.map((m) => (m.model ? { model: m.model } : undefined)));
        setChatId(d.id);
        setTitle(d.title);
        setNotice("");
        return d;
      } catch (err) {
        if ((err as Error).message === "unauthorized") onUnauthorized();
        else {
          setNotice("대화를 불러오지 못했어요.");
          onChanged(); // maybe it was deleted elsewhere: reload the list
        }
        return null;
      }
    },
    [onUnauthorized, onChanged],
  );

  const rename = useCallback(
    async (next: string) => {
      const t = next.trim();
      if (!chatId || !t) return;
      try {
        await renameChat(chatId, t);
        setTitle(t);
        onChanged();
      } catch (err) {
        if ((err as Error).message === "unauthorized") onUnauthorized();
        else setNotice("이름을 바꾸지 못했어요.");
      }
    },
    [chatId, onUnauthorized, onChanged],
  );

  /** Deletes chats on the server. Call ONLY after the user pressed 삭제 in the confirmation window. */
  const removeChats = useCallback(
    async (ids: string[]) => {
      try {
        for (const id of ids) await deleteChat(id);
        if (chatId && ids.includes(chatId)) reset();
      } catch (err) {
        if ((err as Error).message === "unauthorized") onUnauthorized();
        else setNotice("삭제하지 못했어요.");
      } finally {
        onChanged();
      }
    },
    [chatId, reset, onUnauthorized, onChanged],
  );

  return { msgs, metas, busy, notice, chatId, title, send, reset, open, rename, removeChats };
}
