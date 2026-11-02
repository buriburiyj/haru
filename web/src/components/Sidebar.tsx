import { useEffect, useState } from "react";
import type { ChatHistoryItem } from "../types";
import SidebarMenu from "./sidebar/SidebarMenu";
import UserMenu from "./sidebar/UserMenu";
import Overlays from "./Overlays";
import { BackIcon, ChatIcon, CodeIcon, ForwardIcon, PanelIcon } from "./sidebar/icons";

export type SidebarProps = {
  recent: ChatHistoryItem[];
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

export default function Sidebar({ recent, onNew: onNewProp, userName, onLogout, open: openProp, onClose: onCloseProp }: SidebarProps) {
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
  const iconBtn = "flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg";
  const tabCls = (on: boolean) =>
    "flex h-7 w-8 items-center justify-center rounded-md " + (on ? "bg-bg text-fg" : "text-muted");

  return (
    <>
      <Overlays />
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
          <button type="button" onClick={onClose} aria-label="사이드바 접기" className={iconBtn}>
            <PanelIcon />
          </button>
          <button type="button" aria-label="뒤로" className={iconBtn}>
            <BackIcon />
          </button>
          <button type="button" aria-label="앞으로" className={iconBtn}>
            <ForwardIcon />
          </button>
          <div className="ml-auto flex rounded-lg bg-surface-2 p-0.5">
            <button type="button" aria-label="Chat" onClick={() => setTab("chat")} className={tabCls(tab === "chat")}>
              <ChatIcon />
            </button>
            <button type="button" aria-label="Code" onClick={() => setTab("code")} className={tabCls(tab === "code")}>
              <CodeIcon />
            </button>
          </div>
        </div>
        <SidebarMenu recent={recent} onNew={onNewProp} />
        <UserMenu userName={userName} onLogout={onLogout} />
      </aside>
    </>
  );
}
