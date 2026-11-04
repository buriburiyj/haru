import { useEffect, useMemo, useRef, useState } from "react";
import { copyText } from "../chat/ActionButton";
import { Button, Tabs } from "../ui";
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

  return (
    <aside className="fixed inset-0 z-50 flex flex-col bg-bg text-fg md:static md:inset-auto md:z-auto md:w-md md:shrink-0 md:border-l md:border-line">
      <header className="flex items-center gap-2 border-b border-line px-3 py-2">
        <h2 className="min-w-0 flex-1 truncate text-sm font-medium">{artifact.title}</h2>
        <Tabs
          value={tab}
          onChange={setTab}
          options={[
            { id: "preview", label: "미리보기" },
            { id: "code", label: "코드" },
          ]}
        />
        <Button variant="ghost" className="px-2 text-muted" onClick={() => copyText(artifact.code)}>
          복사
        </Button>
        <Button variant="ghost" className="px-2 text-muted" onClick={onClose}>
          닫기
        </Button>
      </header>

      {error && (
        <div className="flex items-center gap-2 border-b border-line bg-surface px-3 py-2 text-sm">
          <span className="min-w-0 flex-1 truncate text-danger">{error}</span>
          {onFix && (
            <Button variant="primary" className="shrink-0" onClick={() => onFix(error)}>
              Haru로 고치기
            </Button>
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
