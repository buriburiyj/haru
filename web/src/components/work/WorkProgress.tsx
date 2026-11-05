import { useState } from "react";
import type { ReactNode } from "react";
import { Button, Card, CheckIcon, ChevronIcon, CrossIcon, MinusIcon, UndoIcon, cx } from "../ui";
import ConfirmDialog from "../confirm/ConfirmDialog";
import type { StepStatus, WorkAction, WorkRun, WorkSummary } from "../../work/types";

function Dot() {
  return <span aria-hidden="true" className="inline-block h-2 w-2 shrink-0 animate-pulse rounded-pill bg-accent" />;
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="shrink-0 rounded-pill border border-line px-2 text-xs text-muted">{children}</span>
  );
}

function StatusIcon({ status }: { status: StepStatus }) {
  const box = "flex h-5 w-5 shrink-0 items-center justify-center";
  if (status === "running")
    return (
      <span className={box}>
        <Dot />
      </span>
    );
  if (status === "done")
    return (
      <span className={cx(box, "text-muted")}>
        <CheckIcon size={16} />
      </span>
    );
  if (status === "failed")
    return (
      <span className={cx(box, "text-danger")}>
        <CrossIcon size={16} />
      </span>
    );
  if (status === "skipped")
    return (
      <span className={cx(box, "text-muted")}>
        <MinusIcon size={16} />
      </span>
    );
  return (
    <span className={box}>
      <span aria-hidden="true" className="h-3 w-3 rounded-pill border border-line" />
    </span>
  );
}

function DetailView({ detail }: { detail: NonNullable<WorkAction["detail"]> }) {
  const pre = "mt-1 ml-8 overflow-x-auto rounded-control border border-line bg-surface p-3 font-mono text-xs";
  if (detail.kind === "output") return <pre className={cx(pre, "text-fg-2")}>{detail.text}</pre>;
  return (
    <pre className={pre}>
      {detail.text.split("\n").map((line, i) => (
        <div
          key={i}
          className={line.startsWith("+") ? "text-accent-strong" : line.startsWith("-") ? "text-danger" : "text-muted"}
        >
          {line || " "}
        </div>
      ))}
    </pre>
  );
}

function ActionRow({ a, onAskRewind }: { a: WorkAction; onAskRewind: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const failed = a.status === "failed";
  const skipped = a.status === "skipped";
  const labelClass = failed ? "text-danger" : skipped || a.interjection ? "text-muted" : "text-fg";
  const body = (
    <>
      <StatusIcon status={a.status} />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          {a.interjection && <Badge>끼어들기</Badge>}
          <span className={cx("text-sm", labelClass)}>{a.label}</span>
          {a.outward && <Badge>되돌릴 수 없음</Badge>}
        </span>
        {a.interjection && <span className="block text-xs text-muted">현재 행동이 끝나면 반영됩니다</span>}
        {failed && a.reason && <span className="block text-xs text-danger">이유: {a.reason}</span>}
        {skipped && a.reason && <span className="block text-xs text-muted">건너뜀: {a.reason}</span>}
      </span>
      {a.detail && (
        <span className={cx("shrink-0 text-muted transition-transform", expanded && "rotate-180")}>
          <ChevronIcon size={16} />
        </span>
      )}
    </>
  );
  const rowClass = "flex w-full items-start gap-3 py-1.5 text-left pointer-coarse:min-h-11";
  return (
    <li>
      {a.detail ? (
        <button type="button" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)} className={rowClass}>
          {body}
        </button>
      ) : (
        <div className={rowClass}>{body}</div>
      )}
      {expanded && a.detail && <DetailView detail={a.detail} />}
      {a.checkpoint && !a.outward && (
        <div className="ml-8">
          <Button variant="ghost" className="text-muted" onClick={() => onAskRewind(a.id)}>
            <UndoIcon size={16} />
            이 시점으로 되돌리기
          </Button>
        </div>
      )}
    </li>
  );
}

function Section({ title, empty, children }: { title: string; empty: boolean; children: ReactNode }) {
  return (
    <section>
      <h4 className="mb-1 text-sm font-medium text-fg">{title}</h4>
      {empty ? <p className="text-sm text-muted">없음</p> : children}
    </section>
  );
}

function SummaryCard({ s }: { s: WorkSummary }) {
  return (
    <Card className="space-y-4">
      <Section title="한 일" empty={s.did.length === 0}>
        <ul className="list-disc space-y-0.5 pl-5 text-sm text-fg-2">
          {s.did.map((t, i) => (
            <li key={i}>{t}</li>
          ))}
        </ul>
      </Section>
      <Section title="바뀐 파일" empty={s.files.length === 0}>
        <ul className="space-y-1">
          {s.files.map((f, i) => (
            <li key={i} className="flex items-center gap-2 text-sm text-fg-2">
              <span className="min-w-0 break-all">{f.name}</span>
              <Badge>{f.change}</Badge>
            </li>
          ))}
        </ul>
      </Section>
      <Section title="건너뛴 것" empty={s.skipped.length === 0}>
        <ul className="space-y-1">
          {s.skipped.map((k, i) => (
            <li key={i} className="text-sm text-fg-2">
              {k.text} <span className="text-muted">({k.reason})</span>
            </li>
          ))}
        </ul>
      </Section>
      <Section title="쓴 무료 한도" empty={s.usage.length === 0}>
        <ul className="space-y-0.5">
          {s.usage.map((u, i) => (
            <li key={i} className="text-sm text-fg-2">
              {u.label}: {u.value}
            </li>
          ))}
        </ul>
      </Section>
    </Card>
  );
}

function currentAction(actions: WorkAction[]): WorkAction | undefined {
  const running = actions.find((a) => a.status === "running");
  if (running) return running;
  const nonPending = actions.filter((a) => a.status !== "pending");
  return nonPending.length ? nonPending[nonPending.length - 1] : actions[0];
}

/** Progress of one run: checklist, action list, summary. One line on phone, all open on desktop. */
export default function WorkProgress({ run, onRewind }: { run: WorkRun; onRewind?: (actionId: string) => void }) {
  const [open, setOpen] = useState(false);
  const [rewindId, setRewindId] = useState<string | null>(null);
  const working = run.state === "working";
  const firstOpenTodo = run.todos.find((t) => !t.done);
  const cur = currentAction(run.actions);
  const oneLine = run.state === "done" ? "끝났습니다 · 요약 보기" : (cur?.label ?? "");

  return (
    <div>
      <Button variant="secondary" className="w-full justify-between md:hidden" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className="flex min-w-0 items-center gap-2">
          {working && <Dot />}
          <span className="truncate">{oneLine}</span>
        </span>
        <span className={cx("shrink-0 transition-transform", open && "rotate-180")}>
          <ChevronIcon size={16} />
        </span>
      </Button>

      <div className={cx("mt-3 space-y-4 md:mt-0", open ? "block" : "hidden md:block")}>
        {run.todos.length > 0 && (
          <ul className="space-y-1">
            {run.todos.map((t) => (
              <li key={t.id} className="flex items-center gap-3 py-0.5 pointer-coarse:min-h-11">
                <span
                  className={cx(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-pill border border-line",
                    t.done ? "bg-surface-2 text-muted" : "bg-surface",
                  )}
                >
                  {t.done && <CheckIcon size={12} />}
                </span>
                <span className={cx("text-sm", t.done ? "text-muted line-through" : "text-fg")}>{t.text}</span>
                {working && t === firstOpenTodo && <Dot />}
              </li>
            ))}
          </ul>
        )}

        <ul>
          {run.actions.map((a) => (
            <ActionRow key={a.id} a={a} onAskRewind={setRewindId} />
          ))}
        </ul>

        {run.summary && <SummaryCard s={run.summary} />}
      </div>

      {rewindId && (
        <ConfirmDialog
          title="이 체크포인트로 되돌릴까요?"
          message="이후에 바뀐 파일이 이 시점의 상태로 돌아갑니다. 밖으로 보낸 행동은 되돌릴 수 없습니다."
          confirmLabel="되돌리기"
          danger={false}
          onCancel={() => setRewindId(null)}
          onConfirm={() => {
            onRewind?.(rewindId);
            setRewindId(null);
          }}
        />
      )}
    </div>
  );
}
