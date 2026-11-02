/** "‹ 1/2 ›" switcher for edited branches (controlled). Render only when total > 1. idx is 1-based. */
export default function BranchSwitcher({ idx, total, onChange }: { idx: number; total: number; onChange: (idx: number) => void }) {
  if (total <= 1) return null;
  const btn = "px-1 text-muted hover:text-fg disabled:opacity-40";
  return (
    <div className="flex items-center gap-0.5 text-xs text-muted">
      <button type="button" className={btn} disabled={idx <= 1} onClick={() => onChange(idx - 1)} aria-label="이전 버전">
        ‹
      </button>
      <span>
        {idx}/{total}
      </span>
      <button type="button" className={btn} disabled={idx >= total} onClick={() => onChange(idx + 1)} aria-label="다음 버전">
        ›
      </button>
    </div>
  );
}
