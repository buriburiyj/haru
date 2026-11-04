import { useEffect, useState } from "react";
import { getUploadUrl } from "../../api";
import ActionButton, { copyText } from "./ActionButton";
import BranchSwitcher from "./BranchSwitcher";
import { Button, Textarea, UserBubble } from "../ui";

// Edited versions are kept locally for now (old versions are never deleted).
// Later the real branch tree comes from the chat file via useChat.
function Photos({ ids }: { ids: string[] }) {
  const [urls, setUrls] = useState<(string | null)[]>([]);
  const key = ids.join(",");
  useEffect(() => {
    let alive = true;
    const made: string[] = [];
    setUrls([]);
    ids.forEach((id, i) => {
      getUploadUrl(id)
        .then((u) => {
          if (!alive) return URL.revokeObjectURL(u);
          made.push(u);
          setUrls((a) => Object.assign([...a], { [i]: u }));
        })
        .catch(() => alive && setUrls((a) => Object.assign([...a], { [i]: null })));
    });
    return () => {
      alive = false;
      made.forEach((u) => URL.revokeObjectURL(u));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return (
    <div className="flex flex-wrap justify-end gap-2">
      {ids.map((id, i) =>
        urls[i] ? (
          <img key={id + i} src={urls[i]!} alt="첨부한 사진" className="size-20 rounded-control object-cover" />
        ) : urls[i] === null ? (
          <span key={id + i} className="text-xs text-muted">
            사진을 불러오지 못했습니다
          </span>
        ) : (
          <span key={id + i} className="size-20 animate-pulse rounded-control bg-surface-2" aria-hidden="true" />
        ),
      )}
    </div>
  );
}

export default function UserMessage({ content, time, images }: { content: string; time?: string; images?: string[] }) {
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
      {images && images.length > 0 && <Photos ids={images} />}
      {editing ? (
        <div className="w-full max-w-5/6">
          <Textarea
            autoFocus
            rows={3}
            aria-label="메시지 편집"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setEditing(false);
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save();
            }}
            className="block resize-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <Button onClick={() => setEditing(false)}>취소</Button>
            <Button variant="primary" onClick={save}>
              저장
            </Button>
          </div>
        </div>
      ) : (
        <div className="w-full">
          <UserBubble>{shown}</UserBubble>
        </div>
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
