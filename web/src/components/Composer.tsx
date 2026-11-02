import type { ComposerProps } from "../types";

// STUB - owner: composer agent. Keep the ComposerProps contract (src/types.ts).
export default function Composer({ value, onChange, onSubmit, busy }: ComposerProps) {
  return (
    <form
      className="w-full max-w-2xl"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <input
        className="w-full rounded-2xl border border-line bg-surface px-4 py-3"
        aria-label="메시지 입력"
        value={value}
        disabled={busy}
        onChange={(e) => onChange(e.target.value)}
      />
    </form>
  );
}
