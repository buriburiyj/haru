import { useEffect, useState } from "react";

export default function NewProjectDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [folder, setFolder] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const input = "min-h-11 w-full rounded-lg border border-line bg-surface px-3 py-3 text-sm text-fg outline-none";

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-center bg-fg/40 md:items-center md:p-6" onClick={onClose}>
      <form
        role="dialog"
        aria-modal="true"
        aria-label="새 프로젝트"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) onClose();
        }}
        className="flex w-full flex-col bg-bg text-fg md:max-w-lg md:rounded-2xl md:border md:border-line"
      >
        <h2 className="border-b border-line px-4 py-3 text-lg font-semibold">새 프로젝트</h2>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
          <label className="block space-y-1">
            <span className="text-sm text-muted">이름</span>
            <input className={input} value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </label>
          <label className="block space-y-1">
            <span className="text-sm text-muted">목표</span>
            <textarea className={input} rows={4} value={goal} onChange={(e) => setGoal(e.target.value)} />
          </label>
          <label className="block space-y-1">
            <span className="text-sm text-muted">폴더 연결</span>
            <input
              className={input}
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              placeholder="jun-files/projects/…"
            />
            <span className="block text-xs text-muted">폴더는 jun-files 저장소 안에 만들어져요.</span>
          </label>
        </div>
        <div className="flex justify-end gap-2 border-t border-line px-4 py-3">
          <button type="button" onClick={onClose} className="min-h-11 rounded-lg px-4 py-3 text-sm text-muted hover:text-fg">
            취소
          </button>
          <button
            type="submit"
            disabled={!name.trim()}
            className="min-h-11 rounded-lg bg-accent px-5 py-3 text-sm font-medium text-accent-fg disabled:opacity-40"
          >
            만들기
          </button>
        </div>
      </form>
    </div>
  );
}
