import { copyText } from "../chat/ActionButton";
import type { ArtifactData } from "../artifact/types";

const PREVIEW_LANGS = ["html", "svg"];

export default function CodeBlock({
  lang,
  code,
  onOpenArtifact,
}: {
  lang: string;
  code: string;
  onOpenArtifact?: (a: ArtifactData) => void;
}) {
  const l = lang.toLowerCase();
  const canPreview = !!onOpenArtifact && PREVIEW_LANGS.includes(l);
  const btn = "rounded-md px-1.5 py-0.5 text-xs text-muted hover:bg-surface hover:text-fg";
  return (
    <div className="my-2 w-full overflow-hidden rounded-lg border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line bg-surface-2 px-3 py-1">
        <span className="text-xs text-muted">{lang || "text"}</span>
        <div className="flex items-center gap-1">
          {canPreview && (
            <button type="button" className={btn} onClick={() => onOpenArtifact?.({ title: `${l.toUpperCase()} 미리보기`, lang: l, code })}>
              미리보기
            </button>
          )}
          <button type="button" className={btn} onClick={() => copyText(code)}>
            복사
          </button>
        </div>
      </div>
      <pre className="overflow-x-auto p-3 text-sm leading-relaxed text-fg">
        <code>{code}</code>
      </pre>
    </div>
  );
}
