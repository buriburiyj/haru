import { IconButton } from "../ui";

/** "‹ 1/2 ›" switcher for edited branches (controlled). Render only when total > 1. idx is 1-based. */
export default function BranchSwitcher({ idx, total, onChange }: { idx: number; total: number; onChange: (idx: number) => void }) {
  if (total <= 1) return null;
  return (
    <div className="flex items-center gap-0.5 text-xs text-muted">
      <IconButton label="이전 버전" disabled={idx <= 1} onClick={() => onChange(idx - 1)} className="disabled:opacity-40">
        ‹
      </IconButton>
      <span>
        {idx}/{total}
      </span>
      <IconButton label="다음 버전" disabled={idx >= total} onClick={() => onChange(idx + 1)} className="disabled:opacity-40">
        ›
      </IconButton>
    </div>
  );
}
