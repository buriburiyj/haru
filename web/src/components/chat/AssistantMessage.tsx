import type { ReactNode } from "react";
import ActionButton, { copyText } from "./ActionButton";
import BranchSwitcher from "./BranchSwitcher";
import Thinking from "./Thinking";
import Markdown from "../markdown/Markdown";
import type { ArtifactData } from "../artifact/types";

type Part = { kind: "think" | "text"; text: string };

/** Split content into <think> parts and normal text; an unclosed <think> runs to the end. */
function splitThink(content: string): Part[] {
  const parts: Part[] = [];
  let rest = content;
  while (rest) {
    const s = rest.indexOf("<think>");
    if (s < 0) {
      parts.push({ kind: "text", text: rest });
      break;
    }
    if (s > 0) parts.push({ kind: "text", text: rest.slice(0, s) });
    rest = rest.slice(s + 7);
    const e = rest.indexOf("</think>");
    if (e < 0) {
      parts.push({ kind: "think", text: rest });
      break;
    }
    parts.push({ kind: "think", text: rest.slice(0, e) });
    rest = rest.slice(e + 8);
  }
  return parts.filter((p) => p.kind === "think" || p.text.trim());
}

export default function AssistantMessage({
  content,
  pending,
  branches = 1,
  branchIdx = 1,
  onBranchChange,
  onOpenArtifact,
  modelName,
}: {
  content: string;
  pending: boolean;
  branches?: number;
  branchIdx?: number;
  onBranchChange?: (idx: number) => void;
  onOpenArtifact?: (a: ArtifactData) => void;
  /** which model answered, e.g. "자동 · Groq"; wired to the server data later */
  modelName?: string;
}) {
  const body: ReactNode[] = splitThink(content).map((p, i) =>
    p.kind === "think" ? <Thinking key={i} text={p.text} /> : <Markdown key={i} text={p.text} onOpenArtifact={onOpenArtifact} />,
  );
  return (
    <div className="group flex w-full flex-col items-start gap-1">
      {content ? (
        <div className="w-full max-w-full">{body}</div>
      ) : (
        pending && <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-muted" aria-label="응답 중" />
      )}
      {content && !pending && modelName && <span className="text-xs text-muted">{modelName}</span>}
      {branches > 1 && <BranchSwitcher idx={branchIdx} total={branches} onChange={(n) => onBranchChange?.(n)} />}
      {content && (
        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <ActionButton label="복사" onClick={() => copyText(content)}>
            복사
          </ActionButton>
          <ActionButton label="좋아요">👍</ActionButton>
          <ActionButton label="싫어요">👎</ActionButton>
          <ActionButton label="다시 생성">다시 생성</ActionButton>
        </div>
      )}
    </div>
  );
}
