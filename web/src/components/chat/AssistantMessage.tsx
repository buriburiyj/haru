import { useState } from "react";
import type { ReactNode } from "react";
import ActionButton, { copyText } from "./ActionButton";
import BranchSwitcher from "./BranchSwitcher";
import Thinking from "./Thinking";
import Markdown from "../markdown/Markdown";
import type { Source } from "../../api";
import type { ArtifactData } from "../artifact/types";
import { CopyIcon, RefreshIcon, Reply, ThumbDownIcon, ThumbUpIcon } from "../ui";

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
  sources,
}: {
  content: string;
  pending: boolean;
  branches?: number;
  branchIdx?: number;
  onBranchChange?: (idx: number) => void;
  onOpenArtifact?: (a: ArtifactData) => void;
  /** which model answered, e.g. "자동 · Groq"; wired to the server data later */
  modelName?: string;
  /** web search results / GitHub files used for the answer */
  sources?: Source[];
}) {
  // Like / dislike: pressing fills the icon, pressing again clears it (kept locally; sending the vote to the server comes later)
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const body: ReactNode[] = splitThink(content).map((p, i) =>
    p.kind === "think" ? <Thinking key={i} text={p.text} /> : <Markdown key={i} text={p.text} onOpenArtifact={onOpenArtifact} />,
  );
  return (
    <div className="group flex w-full flex-col items-start gap-1">
      {content ? (
        <Reply className="max-w-full">{body}</Reply>
      ) : (
        pending && <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-pill bg-muted" aria-label="응답 중" />
      )}
      {content && !pending && modelName && <span className="text-xs text-muted">{modelName}</span>}
      {content && !pending && sources && sources.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          <span>출처</span>
          {sources.map((src, i) => (
            <a
              key={i}
              href={src.url}
              target="_blank"
              rel="noreferrer noopener"
              title={src.title}
              className="max-w-48 truncate underline hover:text-fg-2"
            >
              {src.title || src.url}
            </a>
          ))}
        </div>
      )}
      {branches > 1 && <BranchSwitcher idx={branchIdx} total={branches} onChange={(n) => onBranchChange?.(n)} />}
      {content && (
        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <ActionButton label="복사" onClick={() => copyText(content)}>
            <CopyIcon size={16} />
          </ActionButton>
          <ActionButton label="좋아요" pressed={vote === "up"} onClick={() => setVote((v) => (v === "up" ? null : "up"))}>
            <ThumbUpIcon size={16} filled={vote === "up"} />
          </ActionButton>
          <ActionButton label="싫어요" pressed={vote === "down"} onClick={() => setVote((v) => (v === "down" ? null : "down"))}>
            <ThumbDownIcon size={16} filled={vote === "down"} />
          </ActionButton>
          <ActionButton label="다시 생성">
            <RefreshIcon size={16} />
          </ActionButton>
        </div>
      )}
    </div>
  );
}
