import { useState } from "react";
import ActionButton, { copyText } from "./ActionButton";
import BranchSwitcher from "./BranchSwitcher";

// Edited versions are kept locally for now (old versions are never deleted).
// Later the real branch tree comes from the chat file via useChat.
export default function UserMessage({ content, time }: { content: string; time?: string }) {
  const [versions, setVersions] = useState<string[]>([content]);
  const [idx, setIdx] = useState(1);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const shown = versions[idx - 1] ?? content;

  const startEdit = () => {
    setDraft(shown);
    setEditing(true);
  };
  const save = () => {
    const t = draft.trim();
    setEditing(false);
    if (!t || t === shown) return;
    setVersions((v) => [...v, t]);
    setIdx(versions.length + 1);
  };

  return (
    <div className="group flex flex-col items-end gap-1">
      {editing ? (
        <div className="w-full max-w-[85%] rounded-2xl border border-line bg-surface p-3 focus-within:border-accent">
          <textarea
            autoFocus
            rows={3}
            aria-label="메시지 편집"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setEditing(false);
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save();
            }}
            className="block w-full resize-none bg-transparent text-fg outline-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button type="button" onClick={() => setEditing(false)} className="rounded-lg border border-line px-3 py-1 text-sm text-fg hover:bg-surface-2">
              취소
            </button>
            <button type="button" onClick={save} className="rounded-lg bg-accent px-3 py-1 text-sm text-accent-fg">
              저장
            </button>
          </div>
        </div>
      ) : (
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl bg-bubble px-4 py-2.5 text-fg">{shown}</div>
      )}
      {!editing && (
        <div className="flex items-center gap-1 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
          <span className="px-1 text-xs text-muted">{time ?? "방금"}</span>
          <ActionButton label="다시 보내기">다시 보내기</ActionButton>
          <ActionButton label="편집" onClick={startEdit}>
            편집
          </ActionButton>
          <ActionButton label="복사" onClick={() => copyText(shown)}>
            복사
          </ActionButton>
        </div>
      )}
      <BranchSwitcher idx={idx} total={versions.length} onChange={setIdx} />
    </div>
  );
}
