import { useState } from "react";
import { Button, Card, CopyIcon, DownloadIcon, ExternalIcon, FileIcon } from "../ui";
import BranchSwitcher from "../chat/BranchSwitcher";
import { copyText } from "../chat/ActionButton";
import type { ArtifactData } from "../artifact/types";
import { formatSize } from "../../work/types";
import type { WorkFile } from "../../work/types";

/** File card (결과물 저장): top part opens the artifact panel, buttons download / copy / open in jun-files. */
export default function FileCard({ file, onOpen }: { file: WorkFile; onOpen: (a: ArtifactData) => void }) {
  const total = file.versions.length;
  // 1-based; default is the newest version
  const [idx, setIdx] = useState(total);
  const version = file.versions[Math.min(Math.max(idx, 1), total) - 1];
  if (!version) return null;
  const size = new TextEncoder().encode(version.text).length;

  const download = () => {
    const url = URL.createObjectURL(new Blob([version.text], { type: "text/plain;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="flex flex-col gap-3">
      <button
        type="button"
        onClick={() => onOpen({ title: file.name, lang: version.lang, code: version.text })}
        className="flex min-w-0 items-center gap-3 rounded-control text-left pointer-coarse:min-h-11 hover:bg-surface-2"
      >
        <span className="shrink-0 text-muted">
          <FileIcon size={24} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-fg">{file.name}</span>
          <span className="block truncate text-xs text-muted">
            {file.kind} · {formatSize(size)} · {version.when}
          </span>
        </span>
      </button>
      <div className="flex flex-wrap items-center gap-2">
        <Button className="text-xs" onClick={download}>
          <DownloadIcon size={16} />
          다운로드
        </Button>
        <Button className="text-xs" onClick={() => copyText(version.text)}>
          <CopyIcon size={16} />
          복사
        </Button>
        <Button
          className="text-xs"
          onClick={() => window.open("https://github.com/buriburiyj/jun-files/blob/main/" + file.path, "_blank", "noopener,noreferrer")}
        >
          <ExternalIcon size={16} />
          jun-files에서 열기
        </Button>
        {total > 1 && (
          <div className="ml-auto">
            <BranchSwitcher idx={idx} total={total} onChange={setIdx} />
          </div>
        )}
      </div>
    </Card>
  );
}
