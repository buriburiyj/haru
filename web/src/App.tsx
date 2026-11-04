import { useCallback, useEffect, useRef, useState } from "react";
import { logout } from "./api";
import { useAttachments } from "./hooks/useAttachments";
import { useAuth } from "./hooks/useAuth";
import { useChat } from "./hooks/useChat";
import { useChatList } from "./hooks/useChatList";
import { useModels } from "./hooks/useModels";
import Sidebar from "./components/Sidebar";
import Welcome from "./components/Welcome";
import Composer from "./components/Composer";
import ChatView from "./components/ChatView";
import LoginScreen from "./components/LoginScreen";
import { useTempChat } from "./components/temp/TempChat";
import type { Effort, ModelId, Mode } from "./types";

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

  if (auth.authed === null) return <main className="h-full" />;
  if (!auth.authed) {
    return <LoginScreen error={auth.error} onSignIn={auth.signIn} onRegister={auth.registerDevice} />;
  }

  const submit = () => {
    const t = text;
    const images = photos.readyIds;
    setText("");
    photos.clear();
    void chat.send(t, { mode: model, web: web ? "auto" : "off", images });
  };

  const composer = (
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
      hideModeSwitch={chat.msgs.length > 0}
      models={models}
      attachments={photos.attachments}
      onAttach={photos.add}
      onRemoveAttachment={photos.remove}
      attachNotice={photos.notice}
      web={web}
      onWebChange={setWeb}
    />
  );

  return (
    <div className="flex h-full bg-bg text-fg">
      <Sidebar
        chats={list.chats}
        activeId={chat.chatId}
        onOpenChat={(id) => void chat.open(id)}
        onDeleteChats={chat.removeChats}
        searchChats={list.search}
        onNew={chat.reset}
        userName="준"
        onLogout={() => {
          logout();
          auth.setAuthed(false);
        }}
        open={drawer}
        onClose={() => setDrawer(false)}
      />
      <main className="min-w-0 flex-1">
        {chat.msgs.length === 0 ? (
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
