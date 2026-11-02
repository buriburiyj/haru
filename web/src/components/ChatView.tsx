import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import type { Msg } from "../types";
import TopBar from "./chat/TopBar";
import UserMessage from "./chat/UserMessage";
import AssistantMessage from "./chat/AssistantMessage";

export type ChatViewProps = {
  msgs: Msg[];
  busy: boolean;
  notice: string;
  title: string;
  /** shown under the input: "Haru도 실수할 수 있습니다 · {modelLabel}" */
  modelLabel: string;
  /** the <Composer/> element, pinned to the bottom */
  composer: ReactNode;
  onMenu: () => void;
};

export default function ChatView({ msgs, busy, notice, title, modelLabel, composer, onMenu }: ChatViewProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const last = msgs[msgs.length - 1];
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [msgs.length, last?.content]);

  return (
    <div className="flex h-full flex-col bg-bg text-fg">
      <TopBar title={title} onMenu={onMenu} />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6">
          {msgs.map((m, i) =>
            m.role === "user" ? (
              <UserMessage key={i} content={m.content} />
            ) : (
              <AssistantMessage key={i} content={m.content} pending={busy && i === msgs.length - 1} />
            ),
          )}
          {notice && <p className="text-xs text-muted">{notice}</p>}
          <div ref={endRef} />
        </div>
      </div>
      <div className="mx-auto w-full max-w-3xl px-4 pb-2">
        {composer}
        <p className="pt-2 text-center text-xs text-muted">Haru도 실수할 수 있습니다 · {modelLabel}</p>
      </div>
    </div>
  );
}
