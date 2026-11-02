import type { ReactNode } from "react";
import type { Msg } from "../types";

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

// STUB - owner: chat-view agent. Keep this props contract.
export default function ChatView({ msgs, notice, composer }: ChatViewProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto p-4">
        {msgs.map((m, i) => (
          <p key={i}>{m.content}</p>
        ))}
        {notice && <p>{notice}</p>}
      </div>
      <div className="p-4">{composer}</div>
    </div>
  );
}
