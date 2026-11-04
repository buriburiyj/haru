import { useState } from "react";
import type { ModelInfo } from "../../api";
import type { Effort, ModelId } from "../../types";
import { Chip, Menu, MenuDivider, MenuItem, SubMenu, WarningIcon } from "../ui";
import { useDismiss } from "./ui";

const HINT: Record<string, string> = {
  auto: "알아서 골라 줍니다",
  groq: "빠른 답변",
  codex: "어려운 질문과 코딩",
  nvidia: "무료 한도를 다 쓰면 대신 답합니다",
};
const EFFORTS: { id: Effort; label: string; hint?: string }[] = [
  { id: "low", label: "낮음" },
  { id: "medium", label: "보통(추천)" },
  { id: "high", label: "높음" },
  { id: "max", label: "최대", hint: "사용량이 많습니다" },
];

export default function ModelMenu({
  model,
  effort,
  models,
  onModelChange,
}: {
  models: ModelInfo[];
  model: ModelId;
  effort: Effort;
  onModelChange: (m: ModelId, e: Effort) => void;
}) {
  const [open, setOpen] = useState(false);
  const close = () => {
    setOpen(false);
  };
  const ref = useDismiss(open, close);
  const pick = (m: ModelId, e: Effort) => {
    onModelChange(m, e);
    close();
  };

  const main = models.filter((m) => m.provider !== "nvidia");
  const more = models.filter((m) => m.provider === "nvidia");
  const label = models.find((m) => m.id === model)?.label ?? model;

  return (
    <div ref={ref} className="relative">
      <Chip caret aria-expanded={open} onClick={() => (open ? close() : setOpen(true))}>
        {label}
      </Chip>
      {open && (
        <Menu className="absolute bottom-full right-0 z-20 mb-2 w-72">
          {main.map((m) => (
            <MenuItem key={m.id} hint={HINT[m.provider]} check={m.id === model} onClick={() => pick(m.id, effort)}>
              {m.label}
            </MenuItem>
          ))}
          <MenuDivider />
          <SubMenu label="노력" side="left">
            {EFFORTS.map((e) => (
              <MenuItem key={e.id} check={e.id === effort} hint={e.hint} icon={e.id === "max" ? <WarningIcon size={16} /> : undefined} onClick={() => pick(model, e.id)}>
                {e.label}
              </MenuItem>
            ))}
          </SubMenu>
          {more.length > 0 && (
          <SubMenu label="더 많은 모델" side="left">
            {more.map((m) => (
              <MenuItem key={m.id} hint={HINT.nvidia} check={m.id === model} onClick={() => pick(m.id, effort)}>
                {m.label}
              </MenuItem>
            ))}
          </SubMenu>
          )}
          <p className="px-3 py-2 text-xs text-muted">무료 한도를 모두 쓰면 다른 모델로 자동 전환됩니다.</p>
        </Menu>
      )}
    </div>
  );
}
