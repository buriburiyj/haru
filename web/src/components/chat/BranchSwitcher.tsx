import { useState } from "react";

/** "‹ 1/2 ›" switcher for edited branches. Render only when total > 1. */
export default function BranchSwitcher({ total }: { total: number }) {
  const [idx, setIdx] = useState(total);
  if (total <= 1) return null;
  const btn = "px-1 text-muted hover:text-fg disabled:opacity-40";
  return (
    <div className="flex items-center gap-0.5 text-xs text-muted">
      <button type="button" className={btn} disabled={idx <= 1} onClick={() => setIdx(idx - 1)} aria-label="이전 버전">
        ‹
      </button>
      <span>
        {idx}/{total}
      </span>
      <button type="button" className={btn} disabled={idx >= total} onClick={() => setIdx(idx + 1)} aria-label="다음 버전">
        ›
      </button>
    </div>
  );
}
