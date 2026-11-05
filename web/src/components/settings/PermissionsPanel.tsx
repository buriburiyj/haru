import { useState } from "react";
import ConfirmDialog from "../confirm/ConfirmDialog";
import { Button, Card } from "../ui";

type Rule = { id: string; tool: string; text: string; scope: string; added: string };

const EXAMPLE: Rule[] = [
  { id: "r1", tool: "GitHub", text: "jun-lab 읽기", scope: "모든 프로젝트", added: "2026년 10월 12일" },
  { id: "r2", tool: "Gmail", text: "받은 편지함 검색", scope: "모든 프로젝트", added: "2026년 10월 20일" },
  { id: "r3", tool: "파일", text: "README.md 수정", scope: "이 프로젝트", added: "2026년 11월 1일" },
  { id: "r4", tool: "터미널", text: "npm test 실행", scope: "이 프로젝트", added: "2026년 11월 3일" },
];

/** 허락 목록: rules the user allowed with [항상 허락]. Static example data. */
export default function PermissionsPanel() {
  const [rules, setRules] = useState<Rule[]>(EXAMPLE);
  const [target, setTarget] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted">삭제·보내기·결제는 항상 허락할 수 없어서 이 목록에 없습니다.</p>
      {rules.length === 0 && <Card className="p-6 text-center text-sm text-muted">항상 허락한 규칙이 없습니다</Card>}
      {rules.map((r) => (
        <Card key={r.id} className="flex items-center gap-3 p-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm text-fg">
              <span className="text-muted">{r.tool}</span> · {r.text}
            </p>
            <p className="mt-0.5 text-xs text-muted">
              {r.scope} · {r.added}
            </p>
          </div>
          <Button onClick={() => setTarget(r.id)}>지우기</Button>
        </Card>
      ))}
      {target && (
        <ConfirmDialog
          title="이 규칙을 지울까요?"
          message="지우면 다음부터 이 행동을 할 때 다시 물어봅니다."
          confirmLabel="지우기"
          onCancel={() => setTarget(null)}
          onConfirm={() => {
            setRules((rs) => rs.filter((r) => r.id !== target));
            setTarget(null);
          }}
        />
      )}
    </div>
  );
}
