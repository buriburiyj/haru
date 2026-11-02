import ActionButton, { copyText } from "./ActionButton";
import BranchSwitcher from "./BranchSwitcher";

export default function AssistantMessage({ content, pending, branches = 1 }: { content: string; pending: boolean; branches?: number }) {
  return (
    <div className="group flex flex-col items-start gap-1">
      {content ? (
        <div className="max-w-full whitespace-pre-wrap break-words text-fg">{content}</div>
      ) : (
        pending && <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-muted" aria-label="응답 중" />
      )}
      {branches > 1 && <BranchSwitcher total={branches} />}
      {content && (
        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <ActionButton label="복사" onClick={() => copyText(content)}>
            복사
          </ActionButton>
          <ActionButton label="좋아요">👍</ActionButton>
          <ActionButton label="싫어요">👎</ActionButton>
          <ActionButton label="다시 생성">다시 생성</ActionButton>
        </div>
      )}
    </div>
  );
}
