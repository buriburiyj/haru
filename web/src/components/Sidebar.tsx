import type { ChatHistoryItem } from "../types";

export type SidebarProps = {
  recent: ChatHistoryItem[];
  onNew: () => void;
  userName: string;
  onLogout: () => void;
  /** phone drawer state; on desktop the sidebar is always visible */
  open: boolean;
  onClose: () => void;
};

// STUB - owner: sidebar agent. Keep this props contract.
export default function Sidebar({ onNew, userName }: SidebarProps) {
  return (
    <aside className="hidden w-64 shrink-0 border-r border-line bg-surface p-3 md:block">
      <button onClick={onNew}>새로 만들기</button>
      <p>{userName}</p>
    </aside>
  );
}
