import { useSyncExternalStore } from "react";

// Temporary (secret) chat flag shared by the toggle and the banner. UI only for now;
// later the app reads isTempChat() before saving a chat or memory.
let on = false;
const listeners = new Set<() => void>();
const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
};
export const isTempChat = () => on;
export const setTempChat = (v: boolean) => {
  on = v;
  listeners.forEach((l) => l());
};
export const useTempChat = () => useSyncExternalStore(subscribe, () => on);

export function TempChatToggle() {
  const active = useTempChat();
  return (
    <button
      type="button"
      onClick={() => setTempChat(!active)}
      aria-pressed={active}
      aria-label="임시 채팅"
      title="임시 채팅"
      className={`flex h-11 w-11 items-center justify-center rounded-lg hover:bg-surface-2 ${active ? "text-accent" : "text-muted"}`}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M5 21V11a7 7 0 0 1 14 0v10l-2.500-2-2 2-2.500-2-2.500 2-2-2L5 21Z" />
        <circle cx="9.500" cy="11" r="1" fill="currentColor" />
        <circle cx="14.500" cy="11" r="1" fill="currentColor" />
      </svg>
    </button>
  );
}

export function TempChatBanner() {
  const active = useTempChat();
  if (!active) return null;
  return (
    <div role="status" className="border-b border-line bg-surface px-4 py-1.5 text-center text-xs text-muted">
      기록·기억이 저장되지 않습니다
    </div>
  );
}
