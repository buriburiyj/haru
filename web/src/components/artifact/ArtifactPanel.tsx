import { useEffect, useMemo, useRef, useState } from "react";
import { copyText } from "../chat/ActionButton";
import type { ArtifactData } from "./types";

type Props = {
  artifact: ArtifactData | null;
  onClose: () => void;
  onFix?: (message: string) => void;
};

const ERROR_SCRIPT =
  "<script>window.onerror=function(m){parent.postMessage({type:'haru-error',message:String(m)},'*');};" +
  "window.addEventListener('unhandledrejection',function(e){parent.postMessage({type:'haru-error',message:String(e.reason)},'*');});</script>";

function buildSrcDoc(lang: string, code: string): string | null {
  const l = lang.toLowerCase();
  if (l === "html") return ERROR_SCRIPT + code;
  if (l === "svg") return ERROR_SCRIPT + code;
  return null;
}

export default function ArtifactPanel({ artifact, onClose, onFix }: Props) {
  const [tab, setTab] = useState<"preview" | "code">("preview");
  const [error, setError] = useState<string | null>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);

  const srcDoc = useMemo(
    () => (artifact ? buildSrcDoc(artifact.lang, artifact.code) : null),
    [artifact],
  );

  useEffect(() => {
    setError(null);
    setTab("preview");
  }, [artifact]);

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (e.source !== frameRef.current?.contentWindow) return;
      const d = e.data as { type?: string; message?: string } | null;
      if (d && d.type === "haru-error" && typeof d.message === "string") {
        setError(d.message);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  if (!artifact) return null;

  const tabClass = (active: boolean) =>
    `rounded-md px-3 py-1 text-sm ${active ? "bg-surface-2 text-fg" : "text-muted"}`;

  return (
    <aside className="fixed inset-0 z-50 flex flex-col bg-bg text-fg md:static md:inset-auto md:z-auto md:w-[28rem] md:shrink-0 md:border-l md:border-line">
      <header className="flex items-center gap-2 border-b border-line px-3 py-2">
        <h2 className="min-w-0 flex-1 truncate text-sm font-medium">{artifact.title}</h2>
        <div className="flex gap-1">
          <button type="button" className={tabClass(tab === "preview")} onClick={() => setTab("preview")}>
            미리보기
          </button>
          <button type="button" className={tabClass(tab === "code")} onClick={() => setTab("code")}>
            코드
          </button>
        </div>
        <button
          type="button"
          className="rounded-md px-2 py-1 text-sm text-muted hover:bg-surface-2"
          onClick={() => copyText(artifact.code)}
        >
          복사
        </button>
        <button
          type="button"
          className="rounded-md px-2 py-1 text-sm text-muted hover:bg-surface-2"
          onClick={onClose}
        >
          닫기
        </button>
      </header>

      {error && (
        <div className="flex items-center gap-2 border-b border-line bg-surface px-3 py-2 text-sm">
          <span className="min-w-0 flex-1 truncate text-danger">{error}</span>
          {onFix && (
            <button
              type="button"
              className="shrink-0 rounded-md bg-accent px-3 py-1 text-accent-fg"
              onClick={() => onFix(error)}
            >
              Haru로 고치기
            </button>
          )}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto">
        {tab === "preview" && srcDoc !== null ? (
          <iframe
            ref={frameRef}
            title={artifact.title}
            sandbox="allow-scripts"
            srcDoc={srcDoc}
            className="h-full w-full bg-bg"
          />
        ) : (
          <>
            {tab === "preview" && (
              <p className="border-b border-line bg-surface px-3 py-2 text-sm text-muted">
                이 형식은 미리보기를 지원하지 않습니다
              </p>
            )}
            <pre className="overflow-x-auto bg-surface p-3 font-mono text-sm text-fg">
              <code>{artifact.code}</code>
            </pre>
          </>
        )}
      </div>
    </aside>
  );
}
