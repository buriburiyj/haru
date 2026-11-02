import type { Msg } from "./api";

export type { Msg };
export type ModelId = "auto" | "gpt-6-luna" | "gpt-5.6-terra" | "gpt-5.6-luna" | "fast" | string;
export type Effort = "low" | "medium" | "high" | "max";
export type Mode = "chat" | "cowork";
export type Page = "home" | "chat";

export type ChatHistoryItem = { id: string; title: string; when: string };

/** Shared props for the composer (input box). Owned by components/Composer.tsx. */
export type ComposerProps = {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
  model: ModelId;
  effort: Effort;
  onModelChange: (m: ModelId, e: Effort) => void;
  mode: Mode;
  onModeChange: (m: Mode) => void;
  /** hide the [Chat|Cowork] switch (hidden inside a conversation) */
  hideModeSwitch?: boolean;
};
