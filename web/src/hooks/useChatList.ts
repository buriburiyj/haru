import { useCallback, useEffect, useState } from "react";
import { getChatList } from "../api";
import { toRow, type ChatRow } from "../components/chat/dataTypes";

/** Saved chats, newest first. `search(q)` matches title and preview on the server (used by ⌘K). */
export function useChatList(enabled: boolean) {
  const [chats, setChats] = useState<ChatRow[]>([]);
  const [error, setError] = useState(false);
  // set when the server answered but could not reach its storage (GET /chats warning)
  const [warning, setWarning] = useState<string | undefined>();

  const refresh = useCallback(async () => {
    try {
      const d = await getChatList();
      setChats(d.chats.map(toRow));
      setWarning(d.warning);
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    if (enabled) void refresh();
  }, [enabled, refresh]);

  const search = useCallback(async (q: string): Promise<ChatRow[]> => (await getChatList(q)).chats.map(toRow), []);

  return { chats, error, warning, refresh, search };
}
