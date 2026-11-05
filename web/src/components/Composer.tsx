import { useEffect, useRef, useState } from "react";
import type { ComposerProps } from "../types";
import ModeSwitch from "./composer/ModeSwitch";
import ModelMenu from "./composer/ModelMenu";
import PlusMenu from "./composer/PlusMenu";
import type { ComposerExtras } from "./chat/dataTypes";
import { Button, IconButton, StopIcon } from "./ui";

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
  models,
  attachments,
  onAttach,
  onRemoveAttachment,
  attachNotice,
  web,
  onWebChange,
  working,
  onStop,
}: ComposerProps &
  ComposerExtras & {
    /** the agent is working: typing stays possible (interjection) and the send button becomes ■ 멈춤 while the box is empty */
    working?: boolean;
    onStop?: () => void;
  }) {
  const ta = useRef<HTMLTextAreaElement>(null);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [value]);

  const uploading = attachments.some((a) => a.status === "uploading");
  const hasContent = value.trim().length > 0 || attachments.some((a) => a.status === "ready");
  const canSend = !busy && !uploading && hasContent;
  const showStop = !!working && !!onStop && !hasContent;

  return (
    <form
      className="w-full max-w-2xl rounded-card border border-line bg-surface p-3 transition-colors focus-within:border-accent"
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) onSubmit();
      }}
    >
      {attachments.length > 0 && (
        <div className="mb-2">
          <div className="flex flex-wrap gap-2">
            {attachments.map((a) => (
              <div key={a.key} className="relative size-16 overflow-hidden rounded-control border border-line bg-surface-2">
                <img src={a.previewUrl} alt={a.name} className="size-16 object-cover" />
                {a.status === "uploading" && (
                  <div className="absolute inset-0 flex items-center justify-center bg-bg/70 text-center text-xs text-fg">올리는 중</div>
                )}
                {a.status === "error" && (
                  <div role="img" aria-label="올리지 못했습니다" className="absolute inset-0 flex items-center justify-center bg-bg/70 text-danger">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <circle cx="12" cy="12" r="9" />
                      <path d="M12 8v5M12 16.5v.01" />
                    </svg>
                  </div>
                )}
                <IconButton label="사진 빼기" onClick={() => onRemoveAttachment(a.key)} className="absolute right-0 top-0 !size-6 bg-bg/70 text-xs">
                  ✕
                </IconButton>
              </div>
            ))}
          </div>
          {attachNotice && (
            <p className={`mt-1 text-xs ${attachments.some((a) => a.status === "error") ? "text-danger" : "text-muted"}`}>{attachNotice}</p>
          )}
        </div>
      )}
      <textarea
        ref={ta}
        rows={1}
        aria-label="메시지 입력"
        value={value}
        placeholder={working ? "일하는 중에도 입력할 수 있습니다" : focused ? "/를 입력하면 Skills가 나옵니다" : "무엇을 도와드릴까요?"}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            if (canSend) onSubmit();
          }
        }}
        className="block w-full resize-none bg-transparent px-1 py-1 pointer-coarse:min-h-11 text-fg outline-none placeholder:text-muted"
      />
      <div className="mt-2 flex items-center gap-2">
        <PlusMenu webSearch={web} onToggleWebSearch={() => onWebChange(!web)} onAttach={onAttach} />
        <div className="flex-1" />
        {!hideModeSwitch && <ModeSwitch mode={mode} onChange={onModeChange} />}
        <ModelMenu models={models} model={model} effort={effort} onModelChange={onModelChange} />
        {showStop ? (
          <Button variant="secondary" aria-label="멈춤" title="멈춤" onClick={onStop} className="w-9 pointer-coarse:w-11 px-0">
            <StopIcon size={16} />
          </Button>
        ) : (
          <Button
            type="submit"
            variant="primary"
            aria-label={working ? "끼어들기 보내기" : "보내기"}
            disabled={!canSend}
            className="w-9 pointer-coarse:w-11 px-0"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </Button>
        )}
      </div>
    </form>
  );
}
