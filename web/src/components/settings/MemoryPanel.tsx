import { useCallback, useEffect, useState } from "react";
import { HttpError, deleteMemory, listMemory, updateMemory, type MemoryEntry } from "../../api";
import ConfirmDialog from "../confirm/ConfirmDialog";
import { Button, Card, Dialog, Input, Textarea } from "../ui";

const fmtDate = (sec: number) =>
  new Date(sec * 1000).toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" });

function errText(e: unknown, fallback: string): string {
  if (e instanceof Error && e.message === "unauthorized") return "다시 로그인해 주세요";
  if (e instanceof HttpError && e.status === 400) return "입력이 올바르지 않습니다. 제목은 60자, 내용은 2000자까지입니다.";
  return fallback;
}

function EditDialog({ entry, onClose, onSaved }: { entry: MemoryEntry; onClose: () => void; onSaved: (m: MemoryEntry) => void }) {
  const [topic, setTopic] = useState(entry.topic);
  const [content, setContent] = useState(entry.content);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const save = async () => {
    setBusy(true);
    setErr("");
    try {
      onSaved(await updateMemory(entry.id, { topic: topic.trim(), content: content.trim() }));
    } catch (e) {
      setErr(errText(e, "저장하지 못했습니다"));
      setBusy(false);
    }
  };
  return (
    <Dialog
      title="기억 수정"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>취소</Button>
          <Button variant="primary" disabled={busy || !topic.trim() || !content.trim()} onClick={save}>
            저장
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3 p-4">
        <Input value={topic} maxLength={60} onChange={(e) => setTopic(e.target.value)} aria-label="주제" placeholder="주제" />
        <Textarea value={content} maxLength={2000} rows={6} onChange={(e) => setContent(e.target.value)} aria-label="내용" placeholder="내용" />
        {err && <p className="text-sm text-danger">{err}</p>}
      </div>
    </Dialog>
  );
}

/** Real memory list (GET /memory) with edit and delete. Rendered under the 메모리 생성 switch. */
export default function MemoryPanel() {
  const [items, setItems] = useState<MemoryEntry[] | null>(null);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<MemoryEntry | null>(null);
  const [deleting, setDeleting] = useState<MemoryEntry | null>(null);

  const load = useCallback(() => {
    setItems(null);
    setErr("");
    listMemory().then(setItems, (e) => setErr(errText(e, "기억을 불러오지 못했습니다")));
  }, []);
  useEffect(load, [load]);

  const remove = async () => {
    const m = deleting;
    setDeleting(null);
    if (!m) return;
    try {
      await deleteMemory(m.id);
      setItems((a) => a && a.filter((x) => x.id !== m.id));
    } catch (e) {
      setErr(errText(e, "삭제하지 못했습니다"));
    }
  };

  return (
    <div className="mt-4 flex flex-col gap-3">
      {err ? (
        <div className="flex items-center gap-3 text-sm text-danger">
          <span>{err}</span>
          <Button onClick={load}>다시 시도</Button>
        </div>
      ) : items === null ? (
        <p className="text-sm text-muted">불러오는 중…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted">저장된 기억이 없습니다</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((m) => (
            <li key={m.id}>
              <Card className="flex flex-col gap-2">
                <div className="text-sm font-semibold text-fg">{m.topic}</div>
                <p className="line-clamp-3 whitespace-pre-wrap text-sm text-fg-2">{m.content}</p>
                <div className="flex items-center gap-2">
                  <span className="mr-auto text-xs text-muted">{fmtDate(m.updated)}</span>
                  <Button className="text-xs" onClick={() => setEditing(m)}>
                    수정
                  </Button>
                  <Button className="text-xs text-danger" onClick={() => setDeleting(m)}>
                    삭제
                  </Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted">대화에서 '기억해줘: …'라고 말하면 여기에 저장됩니다.</p>
      {editing && (
        <EditDialog
          entry={editing}
          onClose={() => setEditing(null)}
          onSaved={(n) => {
            setItems((a) => a && a.map((x) => (x.id === n.id ? n : x)));
            setEditing(null);
          }}
        />
      )}
      {deleting && (
        <ConfirmDialog title="기억 삭제" message={`'${deleting.topic}' 기억을 삭제할까요?`} onConfirm={remove} onCancel={() => setDeleting(null)} />
      )}
    </div>
  );
}
