import type { ChatMeta, ModelInfo, Source } from "../../api";

/** Extra data of one message, parallel to the msgs array (index i belongs to msgs[i]). */
export type MsgMeta = {
  /** id of the model that answered (done.model, or Msg.model of an opened chat) */
  model?: string;
  /** the user had "자동" selected when asking: shows "자동 · Groq" */
  auto?: boolean;
  /** web search results and GitHub files used for the answer (done.sources) */
  sources?: Source[];
};

/** A photo chosen in the composer. `id` is set after POST /uploads succeeded. */
export type Attachment = {
  key: string;
  name: string;
  previewUrl: string;
  status: "uploading" | "ready" | "error";
  id?: string;
  error?: string;
};

/** Row for the sidebar, chat list page and search. `when` is a relative date. */
export type ChatRow = {
  id: string;
  title: string;
  when: string;
  preview: string;
  updated: number;
  /** a task or answer is running in this conversation: the sidebar shows a spinning dot */
  working?: boolean;
};

/** Props the composer gets in addition to ComposerProps (src/types.ts). */
export type ComposerExtras = {
  /** GET /models result; the first entry is "자동" */
  models: ModelInfo[];
  attachments: Attachment[];
  /** user picked image files (the hook validates size/type and uploads) */
  onAttach: (files: File[]) => void;
  onRemoveAttachment: (key: string) => void;
  /** message under the previews, e.g. "사진은 3MB까지 올릴 수 있습니다." */
  attachNotice?: string;
  /** web search on (sent as web: "auto") or off */
  web: boolean;
  onWebChange: (v: boolean) => void;
};

export function relativeWhen(unixSeconds: number, now = Date.now()): string {
  const s = Math.max(0, Math.floor(now / 1000 - unixSeconds));
  if (s < 60) return "방금";
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  const d = Math.floor(s / 86400);
  if (d === 1) return "어제";
  if (d < 30) return `${d}일 전`;
  return new Date(unixSeconds * 1000).toLocaleDateString("ko-KR");
}

export const toRow = (c: ChatMeta): ChatRow => ({
  id: c.id,
  title: c.title || "제목 없음",
  when: relativeWhen(c.updated),
  preview: c.preview ?? "",
  updated: c.updated,
});

/** "자동 · Groq" when the user chose 자동, otherwise just the model name. Empty when unknown. */
export function formatModelName(model: string | null | undefined, auto: boolean | undefined, models: ModelInfo[]): string {
  if (!model) return "";
  const m = models.find((x) => x.id === model);
  const name = m ? (m.provider === "groq" ? "Groq" : m.label) : model;
  return auto ? `자동 · ${name}` : name;
}
