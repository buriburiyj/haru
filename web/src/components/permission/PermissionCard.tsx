import { Button, Card } from "../ui";

export type PermissionKind = "normal" | "delete" | "send" | "pay";
export type PermissionRequest = { title: string; kind: PermissionKind; detail?: string };
export type PermissionDecision = "once" | "always" | "deny";

/** Example request, only when the URL has ?demo=permission or ?demo=permission-delete. Returns null otherwise. */
export function demoPermission(): PermissionRequest | null {
  const d = new URLSearchParams(window.location.search).get("demo");
  if (d === "permission") return { title: "GitHub: jun-lab에 파일 3개 올리기", kind: "normal", detail: "파일 3개: README.md, docs/usage.md, scripts/run.py" };
  if (d === "permission-delete") return { title: "GitHub: jun-lab에서 파일 3개 지우기", kind: "delete" };
  return null;
}

const LABEL: Record<PermissionKind, string> = {
  normal: "허용을 요청합니다",
  delete: "삭제는 매번 확인합니다",
  send: "보내기는 매번 확인합니다",
  pay: "결제는 매번 확인합니다",
};

/**
 * Permission request, pinned right above the composer.
 * Delete / send / pay never offer [항상 허락]: they are asked every time.
 */
export default function PermissionCard({
  request,
  onDecide,
}: {
  request: PermissionRequest;
  onDecide: (d: PermissionDecision) => void;
}) {
  return (
    <Card role="alertdialog" aria-label="권한 요청" className="mb-2 p-3">
      <p className="text-xs text-muted">{LABEL[request.kind]}</p>
      <p className="mt-0.5 text-sm text-fg">{request.title}</p>
      {request.detail && <p className="mt-1 text-xs text-muted">{request.detail}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="primary" onClick={() => onDecide("once")}>
          허락
        </Button>
        {request.kind === "normal" && <Button onClick={() => onDecide("always")}>항상 허락</Button>}
        <Button onClick={() => onDecide("deny")} className="text-danger">
          거절
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted">
        {request.kind === "normal" ? "항상 허락은 설정 > 허락 목록에서 지울 수 있습니다." : "삭제·보내기·결제는 매번 물어봅니다."}
      </p>
    </Card>
  );
}
