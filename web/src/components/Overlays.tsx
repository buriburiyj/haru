import { useEffect, useState } from "react";
import SettingsDialog from "./settings/SettingsDialog";
import SearchDialog from "./search/SearchDialog";
import CustomizeDialog from "./customize/CustomizeDialog";
import ChatListPage from "./pages/ChatListPage";
import ProjectsPage from "./pages/ProjectsPage";
import ArtifactsPage from "./pages/ArtifactsPage";
import NewProjectDialog from "./pages/NewProjectDialog";
import { useVisualViewportHeight } from "./useVisualViewportHeight";
import OfflineNotice from "./OfflineNotice";
import type { ChatRow } from "./chat/dataTypes";

export type OverlaysProps = {
  isMacApp?: boolean;
  chats: ChatRow[];
  onOpenChat: (id: string) => void;
  onDeleteChats: (ids: string[]) => void | Promise<void>;
  searchChats: (q: string) => Promise<ChatRow[]>;
};

export default function Overlays({ isMacApp = false, chats, onOpenChat, onDeleteChats, searchChats }: OverlaysProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [page, setPage] = useState<null | "chats" | "projects" | "artifacts">(null);
  const [newProject, setNewProject] = useState(false);
  useVisualViewportHeight();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
      if (e.key === ",") {
        e.preventDefault();
        setSearchOpen(false);
        setSettingsOpen(true);
      } else if (e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSettingsOpen(false);
        setSearchOpen(true);
      }
    };
    const openSettings = () => {
      setSearchOpen(false);
      setSettingsOpen(true);
    };
    const openSearch = () => {
      setSettingsOpen(false);
      setSearchOpen(true);
    };
    const openCustomize = () => {
      setSettingsOpen(false);
      setSearchOpen(false);
      setCustomizeOpen(true);
    };
    const openPage = (p: "chats" | "projects" | "artifacts") => () => setPage(p);
    const onChats = openPage("chats");
    const onProjects = openPage("projects");
    const onArtifacts = openPage("artifacts");
    const onNewProject = () => setNewProject(true);
    const onNewChat = () => setPage(null);
    window.addEventListener("haru:open-chats", onChats);
    window.addEventListener("haru:open-projects", onProjects);
    window.addEventListener("haru:open-artifacts", onArtifacts);
    window.addEventListener("haru:new-project", onNewProject);
    window.addEventListener("haru:new-chat", onNewChat);
    window.addEventListener("keydown", onKey);
    window.addEventListener("haru:open-customize", openCustomize);
    window.addEventListener("haru:open-settings", openSettings);
    window.addEventListener("haru:open-search", openSearch);
    return () => {
      window.removeEventListener("haru:open-chats", onChats);
      window.removeEventListener("haru:open-projects", onProjects);
      window.removeEventListener("haru:open-artifacts", onArtifacts);
      window.removeEventListener("haru:new-project", onNewProject);
      window.removeEventListener("haru:new-chat", onNewChat);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("haru:open-customize", openCustomize);
      window.removeEventListener("haru:open-settings", openSettings);
      window.removeEventListener("haru:open-search", openSearch);
    };
  }, []);

  return (
    <>
      <OfflineNotice />
      {settingsOpen && <SettingsDialog isMacApp={isMacApp} onClose={() => setSettingsOpen(false)} />}
      {searchOpen && <SearchDialog chats={chats} searchChats={searchChats} onOpenChat={onOpenChat} onClose={() => setSearchOpen(false)} />}
      {customizeOpen && <CustomizeDialog onClose={() => setCustomizeOpen(false)} />}
      {page === "chats" && (
        <ChatListPage
          onClose={() => setPage(null)}
          chats={chats.map((c) => ({ id: c.id, title: c.title, kind: "채팅" as const, when: c.when }))}
          onOpen={(id) => {
            onOpenChat(id);
            setPage(null);
          }}
          onDelete={(ids) => void onDeleteChats(ids)}
        />
      )}
      {page === "projects" && <ProjectsPage onClose={() => setPage(null)} onCreate={() => setNewProject(true)} />}
      {page === "artifacts" && <ArtifactsPage onClose={() => setPage(null)} />}
      {newProject && <NewProjectDialog onClose={() => setNewProject(false)} />}
    </>
  );
}
