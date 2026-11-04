import { copyText } from "../chat/ActionButton";
import { Button } from "../ui";
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
  const btn = "min-h-0 px-2 text-xs text-muted hover:text-fg";
  return (
    <div className="my-2 w-full overflow-hidden rounded-control border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line bg-surface-2 px-3 py-1">
        <span className="text-xs text-muted">{lang || "text"}</span>
        <div className="flex items-center gap-1">
          {canPreview && (
            <Button variant="ghost" className={btn} onClick={() => onOpenArtifact?.({ title: `${l.toUpperCase()} 미리보기`, lang: l, code })}>
              미리보기
            </Button>
          )}
          <Button variant="ghost" className={btn} onClick={() => copyText(code)}>
            복사
          </Button>
        </div>
      </div>
      <pre className="overflow-x-auto p-3 font-mono text-sm leading-relaxed text-fg">
        <code>{code}</code>
      </pre>
    </div>
  );
}
