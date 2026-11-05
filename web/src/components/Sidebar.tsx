import { useEffect, useState } from "react";
import type { ChatRow } from "./chat/dataTypes";
import SidebarMenu from "./sidebar/SidebarMenu";
import UserMenu from "./sidebar/UserMenu";
import Overlays from "./Overlays";
import { IconButton } from "./ui";
import { BackIcon, ChatIcon, CodeIcon, ForwardIcon, PanelIcon } from "./sidebar/icons";

export type SidebarProps = {
  chats: ChatRow[];
  activeId?: string;
  onOpenChat: (id: string) => void;
  onDeleteChats: (ids: string[]) => void | Promise<void>;
  searchChats: (q: string) => Promise<ChatRow[]>;
  onNew: () => void;
  userName: string;
  onLogout: () => void;
  /** phone drawer state; on desktop the sidebar is always visible */
  open: boolean;
  onClose: () => void;
};

const CLOSE_DRAWER_EVENTS = [
  "haru:open-search",
  "haru:open-settings",
  "haru:open-customize",
  "haru:open-chats",
  "haru:open-projects",
  "haru:open-artifacts",
  "haru:new-project",
];

export default function Sidebar({ chats, activeId, onOpenChat, onDeleteChats, searchChats, onNew: onNewProp, userName, onLogout, open: openProp, onClose: onCloseProp }: SidebarProps) {
  const [tab, setTab] = useState<"chat" | "code">("chat");
  // The first screen has its own ☰ button, which asks the drawer to open through an event.
  const [local, setLocal] = useState(false);
  const open = openProp || local;
  const onClose = () => {
    setLocal(false);
    onCloseProp();
  };
  useEffect(() => {
    const openDrawer = () => setLocal(true);
    const closeDrawer = () => {
      setLocal(false);
      onCloseProp();
    };
    const newChat = () => {
      setLocal(false);
      onNewProp();
    };
    window.addEventListener("haru:new-chat", newChat);
    window.addEventListener("haru:open-drawer", openDrawer);
    CLOSE_DRAWER_EVENTS.forEach((n) => window.addEventListener(n, closeDrawer));
    return () => {
      window.removeEventListener("haru:new-chat", newChat);
      window.removeEventListener("haru:open-drawer", openDrawer);
      CLOSE_DRAWER_EVENTS.forEach((n) => window.removeEventListener(n, closeDrawer));
    };
  }, [onCloseProp, onNewProp]);
  const tabCls = (on: boolean) =>
    "flex h-7 w-8 pointer-coarse:min-h-11 pointer-coarse:min-w-11 items-center justify-center rounded-control " + (on ? "bg-bg text-fg" : "text-muted");

  return (
    <>
      <Overlays chats={chats} onOpenChat={onOpenChat} onDeleteChats={onDeleteChats} searchChats={searchChats} />
      <div
        onClick={onClose}
        className={
          "fixed inset-0 z-30 bg-fg/40 transition-opacity md:hidden " +
          (open ? "opacity-100" : "pointer-events-none opacity-0")
        }
      />
      <aside
        className={
          "fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col gap-3 border-r border-line bg-surface/80 p-3 backdrop-blur-md transition-transform md:static md:translate-x-0 " +
          (open ? "translate-x-0" : "-translate-x-full")
        }
      >
        <div className="flex items-center gap-1">
          <IconButton label="사이드바 접기" onClick={onClose}>
            <PanelIcon />
          </IconButton>
          <IconButton label="뒤로">
            <BackIcon />
          </IconButton>
          <IconButton label="앞으로">
            <ForwardIcon />
          </IconButton>
          <div className="ml-auto flex rounded-control bg-surface-2 p-0.5">
            <button type="button" aria-label="Chat" onClick={() => setTab("chat")} className={tabCls(tab === "chat")}>
              <ChatIcon />
            </button>
            <button type="button" aria-label="Code" onClick={() => setTab("code")} className={tabCls(tab === "code")}>
              <CodeIcon />
            </button>
          </div>
        </div>
        <SidebarMenu
          chats={chats}
          activeId={activeId}
          onNew={onNewProp}
          onOpenChat={(id) => {
            onOpenChat(id);
            onClose();
          }}
        />
        <UserMenu userName={userName} onLogout={onLogout} />
      </aside>
    </>
  );
}
