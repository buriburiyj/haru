import type { ReactNode } from "react";
import { ClockIcon, ComputerIcon, ShieldIcon } from "../ui";
import { COMPUTER_LABEL, MODE_LABEL, formatElapsed } from "./types";
import type { Computer, PermissionMode, RunState } from "./types";

const STATE_TEXT: Record<Exclude<RunState, "working">, string> = { done: "끝남", failed: "실패", stopped: "멈춤" };

function Pill({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-pill border border-line bg-surface px-3 py-1 text-xs text-muted">
      {icon}
      {children}
    </span>
  );
}

/** Small non-clickable status pills above the composer. */
export default function StatusChips({
  computer,
  mode,
  elapsed,
  state,
}: {
  computer: Computer;
  mode: PermissionMode;
  elapsed: number;
  state: RunState;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Pill icon={<ComputerIcon size={14} />}>{COMPUTER_LABEL[computer]}</Pill>
      <Pill icon={<ShieldIcon size={14} />}>{MODE_LABEL[mode]}</Pill>
      <Pill icon={<ClockIcon size={14} />}>{state === "working" ? formatElapsed(elapsed) : STATE_TEXT[state]}</Pill>
    </div>
  );
}
