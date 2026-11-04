import { useState } from "react";
import type { Effort, ModelId } from "../../types";
import { Chip, Menu, MenuDivider, MenuItem, SubMenu } from "../ui";
import { useDismiss } from "./ui";

const MODELS: { id: ModelId; label: string; desc: string }[] = [
  { id: "auto", label: "자동(기본)", desc: "상황에 맞는 모델을 자동으로 선택" },
  { id: "gpt-6-luna", label: "GPT-6 Luna", desc: "가장 똑똑한 모델, 복잡한 작업에 적합" },
  { id: "gpt-5.6-terra", label: "GPT-5.6 Terra", desc: "균형 잡힌 일상용 모델" },
  { id: "gpt-5.6-luna", label: "GPT-5.6 Luna", desc: "가볍고 빠른 응답" },
  { id: "fast", label: "빠른 답변(Groq)", desc: "가장 빠르게 짧은 답변" },
];
const MORE: { id: ModelId; label: string }[] = [
  { id: "nemotron-3-ultra", label: "Nemotron 3 Ultra" },
  { id: "mistral-large-4", label: "Mistral Large 4" },
  { id: "deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash" },
];
const EFFORTS: { id: Effort; label: string }[] = [
  { id: "low", label: "낮음" },
  { id: "medium", label: "보통(추천)" },
  { id: "high", label: "높음" },
  { id: "max", label: "최대(⚠ 사용량 많음)" },
];

export function modelLabel(id: ModelId): string {
  return [...MODELS, ...MORE].find((m) => m.id === id)?.label ?? id;
}

export default function ModelMenu({
  model,
  effort,
  onModelChange,
}: {
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

  return (
    <div ref={ref} className="relative">
      <Chip caret aria-expanded={open} onClick={() => (open ? close() : setOpen(true))}>
        {modelLabel(model)}
      </Chip>
      {open && (
        <Menu className="absolute bottom-full right-0 z-20 mb-2 w-72">
          {MODELS.map((m) => (
            <MenuItem key={m.id} hint={m.desc} check={m.id === model} onClick={() => pick(m.id, effort)}>
              {m.label}
            </MenuItem>
          ))}
          <MenuDivider />
          <SubMenu label="노력" side="left">
            {EFFORTS.map((e) => (
              <MenuItem key={e.id} check={e.id === effort} onClick={() => pick(model, e.id)}>
                {e.label}
              </MenuItem>
            ))}
          </SubMenu>
          <SubMenu label="더 많은 모델" side="left">
            {MORE.map((m) => (
              <MenuItem key={m.id} check={m.id === model} onClick={() => pick(m.id, effort)}>
                {m.label}
              </MenuItem>
            ))}
          </SubMenu>
          <p className="px-3 py-2 text-xs text-muted">무료 한도를 모두 쓰면 다른 모델로 자동 전환됩니다.</p>
        </Menu>
      )}
    </div>
  );
}
