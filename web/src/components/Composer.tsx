import { useEffect, useRef, useState } from "react";
import type { ComposerProps } from "../types";
import ModeSwitch from "./composer/ModeSwitch";
import ModelMenu from "./composer/ModelMenu";
import PlusMenu from "./composer/PlusMenu";
import { Button } from "./ui";

export default function Composer({
  value,
  onChange,
  onSubmit,
  busy,
  model,
  effort,
  onModelChange,
  mode,
  onModeChange,
  hideModeSwitch,
}: ComposerProps) {
  const ta = useRef<HTMLTextAreaElement>(null);
  const [focused, setFocused] = useState(false);
  const [webSearch, setWebSearch] = useState(false);

  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [value]);

  const canSend = !busy && value.trim().length > 0;

  return (
    <form
      className="w-full max-w-2xl rounded-card border border-line bg-surface p-3 transition-colors focus-within:border-accent"
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) onSubmit();
      }}
    >
      <textarea
        ref={ta}
        rows={1}
        aria-label="메시지 입력"
        value={value}
        placeholder={focused ? "/를 입력하면 Skills가 나옵니다" : "무엇을 도와드릴까요?"}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            if (canSend) onSubmit();
          }
        }}
        className="block w-full resize-none bg-transparent px-1 py-1 text-fg outline-none placeholder:text-muted"
      />
      <div className="mt-2 flex items-center gap-2">
        <PlusMenu webSearch={webSearch} onToggleWebSearch={() => setWebSearch((v) => !v)} />
        <div className="flex-1" />
        {!hideModeSwitch && <ModeSwitch mode={mode} onChange={onModeChange} />}
        <ModelMenu model={model} effort={effort} onModelChange={onModelChange} />
        <Button type="submit" variant="primary" aria-label="보내기" disabled={!canSend} className="w-9 pointer-coarse:w-11 px-0">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </Button>
      </div>
    </form>
  );
}
