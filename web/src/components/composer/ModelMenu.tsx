import { useState } from "react";
import type { Effort, ModelId } from "../../types";
import { Row, panelCls, useDismiss } from "./ui";

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
  const [sub, setSub] = useState<"effort" | "more" | null>(null);
  const close = () => {
    setOpen(false);
    setSub(null);
  };
  const ref = useDismiss(open, close);
  const pick = (m: ModelId, e: Effort) => {
    onModelChange(m, e);
    close();
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => (open ? close() : setOpen(true))}
        className="flex h-8 items-center gap-1 rounded-lg px-2 text-sm text-muted hover:bg-surface-2"
      >
        <span>{modelLabel(model)}</span>
        <span aria-hidden>▾</span>
      </button>
      {open && (
        <div className={`${panelCls} bottom-full right-0 mb-2 w-72`}>
          {MODELS.map((m) => (
            <Row
              key={m.id}
              label={m.label}
              desc={m.desc}
              checked={m.id === model}
              onHover={() => setSub(null)}
              onClick={() => pick(m.id, effort)}
            />
          ))}
          <div className="my-1 border-t border-line" />
          <Row label="노력" arrow onHover={() => setSub("effort")}>
            {sub === "effort" && (
              <div className={`${panelCls} right-full top-0 mr-1`}>
                {EFFORTS.map((e) => (
                  <Row key={e.id} label={e.label} checked={e.id === effort} onClick={() => pick(model, e.id)} />
                ))}
              </div>
            )}
          </Row>
          <Row label="더 많은 모델" arrow onHover={() => setSub("more")}>
            {sub === "more" && (
              <div className={`${panelCls} right-full top-0 mr-1`}>
                {MORE.map((m) => (
                  <Row key={m.id} label={m.label} checked={m.id === model} onClick={() => pick(m.id, effort)} />
                ))}
              </div>
            )}
          </Row>
          <p className="px-3 py-2 text-xs text-muted">
            무료 한도를 모두 쓰면 다른 모델로 자동 전환됩니다.
          </p>
        </div>
      )}
    </div>
  );
}
