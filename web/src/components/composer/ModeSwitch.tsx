import type { Mode } from "../../types";

const OPTIONS: { id: Mode; label: string }[] = [
  { id: "chat", label: "채팅" },
  { id: "work", label: "Work" },
];

export default function ModeSwitch({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <div className="flex rounded-lg bg-surface-2 p-0.5 text-sm">
      {OPTIONS.map((o) => (
        <button
          key={o.id}
          type="button"
          aria-pressed={mode === o.id}
          onClick={() => onChange(o.id)}
          className={`rounded-md px-2.5 py-1 ${mode === o.id ? "bg-surface text-fg" : "text-muted"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
