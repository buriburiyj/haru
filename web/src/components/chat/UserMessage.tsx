import ActionButton, { copyText } from "./ActionButton";
import BranchSwitcher from "./BranchSwitcher";

export default function UserMessage({ content, time, branches = 1 }: { content: string; time?: string; branches?: number }) {
  return (
    <div className="group flex flex-col items-end gap-1">
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl bg-bubble px-4 py-2.5 text-fg">{content}</div>
      <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
        <span className="px-1 text-xs text-muted">{time ?? "방금"}</span>
        <ActionButton label="다시 보내기">다시 보내기</ActionButton>
        <ActionButton label="편집">편집</ActionButton>
        <ActionButton label="복사" onClick={() => copyText(content)}>
          복사
        </ActionButton>
      </div>
      {branches > 1 && <BranchSwitcher total={branches} />}
    </div>
  );
}
