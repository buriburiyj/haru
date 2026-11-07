import { useCallback, useEffect, useRef, useState } from "react";
import { logout } from "./api";
import { useAttachments } from "./hooks/useAttachments";
import { useAuth } from "./hooks/useAuth";
import { useChat } from "./hooks/useChat";
import { useChatList } from "./hooks/useChatList";
import { useModels } from "./hooks/useModels";
import { usePermissionMode } from "./hooks/usePermissionMode";
import Sidebar from "./components/Sidebar";
import Welcome from "./components/Welcome";
import Composer from "./components/Composer";
import ChatView from "./components/ChatView";
import LoginScreen from "./components/LoginScreen";
import PermissionModeMenu from "./components/work/PermissionModeMenu";
import WorkChatView from "./components/work/WorkChatView";
import { sseSource } from "./work/sseSource";
import { ISOLATED } from "./work/types";
import { useTaskThread } from "./work/useTaskThread";
import { relativeWhen, type ChatRow } from "./components/chat/dataTypes";
import { useTempChat } from "./components/temp/TempChat";
import type { Effort, ModelId, Mode } from "./types";

const WORK_ROW_ID = "work-thread";

export default function App() {
  const auth = useAuth();
  const authed = auth.authed === true;
  const onUnauthorized = useCallback(() => auth.setAuthed(false), [auth.setAuthed]);
  const list = useChatList(authed);
  const models = useModels(authed);
  const chat = useChat(onUnauthorized, list.refresh);
  const photos = useAttachments(onUnauthorized);
  const temp = useTempChat();
  const [text, setText] = useState("");
  const [model, setModel] = useState<ModelId>("auto");
  const [effort, setEffort] = useState<Effort>("medium");
  const [mode, setMode] = useState<Mode>("chat");
  const [web, setWeb] = useState(true);
  const [drawer, setDrawer] = useState(false);
  const [permMode, setPermMode] = usePermissionMode();
  const [workOpen, setWorkOpen] = useState(false);
  // Work mode: each message sent starts a task on the server (POST /tasks + SSE). ?demo=work still uses the fake source.
  const thread = useTaskThread(useCallback(({ prompt, mode }) => sseSource({ prompt, mode }), []));

  // Switching temporary chat on or off starts a fresh conversation (a saved chat never turns temporary half way).
  const firstTemp = useRef(true);
  useEffect(() => {
    if (firstTemp.current) {
      firstTemp.current = false;
      return;
    }
    chat.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [temp]);

  // "전부 허용" only works on isolated computers: fall back to "자동" when the running computer is not isolated
  const computer = thread.active?.run.computer ?? "box";
  useEffect(() => {
    if (permMode === "all" && !ISOLATED[computer]) setPermMode("auto");
  }, [permMode, computer, setPermMode]);

  if (auth.authed === null) return <main className="h-full" />;
  if (!auth.authed) {
    return <LoginScreen error={auth.error} onSignIn={auth.signIn} onRegister={auth.registerDevice} />;
  }

  // Work view shows when a Work task was started and no saved chat is open
  const showWork = workOpen && thread.tasks.length > 0 && chat.msgs.length === 0;

  const submit = () => {
    if (mode === "work") {
      const t = text.trim();
      if (!t) return;
      setText("");
      if (thread.working) thread.interject(t); // typing while it works = interjection
      else {
        thread.start(t, permMode);
        setWorkOpen(true);
      }
      return;
    }
    const t = text;
    const images = photos.readyIds;
    setText("");
    photos.clear();
    void chat.send(t, { mode: model, web: web ? "auto" : "off", images });
  };

  const composerBox = (
    <Composer
      value={text}
      onChange={setText}
      onSubmit={submit}
      busy={chat.busy}
      model={model}
      effort={effort}
      onModelChange={(m, e) => {
        setModel(m);
        setEffort(e);
      }}
      mode={mode}
      onModeChange={setMode}
      hideModeSwitch={chat.msgs.length > 0 || showWork}
      working={mode === "work" && thread.working}
      onStop={thread.stop}
      models={models}
      attachments={photos.attachments}
      onAttach={photos.add}
      onRemoveAttachment={photos.remove}
      attachNotice={photos.notice}
      web={web}
      onWebChange={setWeb}
    />
  );

  const composer = (
    <div className="flex w-full max-w-2xl flex-col items-start gap-2">
      {composerBox}
      {mode === "work" && (
        <PermissionModeMenu
          mode={permMode}
          onChange={(m) => {
            setPermMode(m);
            thread.setMode(m);
          }}
          isolated={ISOLATED[computer]}
        />
      )}
    </div>
  );

  // Sidebar list: the Work conversation (if any) on top with a spinning dot while it works; a saved chat that is streaming too
  const rows: ChatRow[] = [
    ...(thread.tasks.length > 0
      ? [{ id: WORK_ROW_ID, title: thread.tasks[0].prompt, when: relativeWhen(Date.now() / 1000), preview: "", updated: Date.now() / 1000, working: thread.working }]
      : []),
    ...list.chats.map((c) => (c.id === chat.chatId && chat.busy ? { ...c, working: true } : c)),
  ];

  const newChat = () => {
    chat.reset();
    setWorkOpen(false);
  };
  const openChat = (id: string) => {
    if (id === WORK_ROW_ID) {
      chat.reset();
      setWorkOpen(true);
      setMode("work");
      return;
    }
    setWorkOpen(false);
    void chat.open(id);
  };

  return (
    <div className="flex h-full bg-bg text-fg">
      <Sidebar
        chats={rows}
        activeId={showWork ? WORK_ROW_ID : chat.chatId}
        onOpenChat={openChat}
        onDeleteChats={(ids) => chat.removeChats(ids.filter((i) => i !== WORK_ROW_ID))}
        searchChats={list.search}
        onNew={newChat}
        userName="준"
        onLogout={() => {
          logout();
          auth.setAuthed(false);
        }}
        open={drawer}
        onClose={() => setDrawer(false)}
      />
      <main className="min-w-0 flex-1">
        {showWork ? (
          <WorkChatView
            tasks={thread.tasks}
            composer={composer}
            onRewind={thread.rewind}
            onDecide={thread.decide}
            onMenu={() => setDrawer(true)}
          />
        ) : chat.msgs.length === 0 ? (
          <Welcome>{composer}</Welcome>
        ) : (
          <ChatView
            msgs={chat.msgs}
            metas={chat.metas}
            models={models}
            busy={chat.busy}
            notice={chat.notice}
            title={chat.title || (temp ? "임시 채팅" : "새 대화")}
            modelLabel={models.find((m) => m.id === model)?.label ?? model}
            composer={composer}
            onMenu={() => setDrawer(true)}
            onRename={chat.chatId ? (t) => void chat.rename(t) : undefined}
            onDelete={chat.chatId ? () => void chat.removeChats([chat.chatId as string]) : undefined}
          />
        )}
      </main>
    </div>
  );
}
