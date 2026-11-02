import { useState } from "react";
import { Row, panelCls, useDismiss } from "./ui";

const SUB: Record<string, string[]> = {
  project: ["프로젝트 없음", "새 프로젝트 만들기"],
  skills: ["등록된 Skills 없음", "Skills 관리"],
  connectors: ["연결된 커넥터 없음", "커넥터 관리"],
};

export default function PlusMenu({
  webSearch,
  onToggleWebSearch,
}: {
  webSearch: boolean;
  onToggleWebSearch: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [sub, setSub] = useState<string | null>(null);
  const close = () => {
    setOpen(false);
    setSub(null);
  };
  const ref = useDismiss(open, close);

  const submenu = (key: string) =>
    sub === key && (
      <div className={`${panelCls} left-full top-0 ml-1`}>
        {SUB[key].map((t) => (
          <Row key={t} label={t} onClick={close} />
        ))}
      </div>
    );

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="추가"
        aria-expanded={open}
        onClick={() => (open ? close() : setOpen(true))}
        className="flex h-8 w-8 items-center justify-center rounded-lg text-lg text-muted hover:bg-surface-2"
      >
        +
      </button>
      {open && (
        <div className={`${panelCls} bottom-full left-0 mb-2`}>
          <Row label="파일 업로드" hint="⌘U" onHover={() => setSub(null)} onClick={close} />
          <Row label="프로젝트에 추가" arrow onHover={() => setSub("project")}>
            {submenu("project")}
          </Row>
          <Row label="Skills" arrow onHover={() => setSub("skills")}>
            {submenu("skills")}
          </Row>
          <Row label="커넥터" arrow onHover={() => setSub("connectors")}>
            {submenu("connectors")}
          </Row>
          <Row label="플러그인 추가" onHover={() => setSub(null)} onClick={close} />
          <Row label="웹 검색" checked={webSearch} onHover={() => setSub(null)} onClick={onToggleWebSearch} />
        </div>
      )}
    </div>
  );
}
