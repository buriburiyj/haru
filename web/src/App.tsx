import { useState } from "react";
import { useAuth } from "./hooks/useAuth";
import { useChat } from "./hooks/useChat";
import Sidebar from "./components/Sidebar";
import Welcome from "./components/Welcome";
import Composer from "./components/Composer";
import ChatView from "./components/ChatView";
import LoginScreen from "./components/LoginScreen";
import type { Effort, ModelId, Mode } from "./types";

const MODEL_LABELS: Record<string, string> = {
  auto: "자동",
  "gpt-6-luna": "GPT-6 Luna",
  "gpt-5.6-terra": "GPT-5.6 Terra",
  "gpt-5.6-luna": "GPT-5.6 Luna",
  fast: "빠른 답변",
};

export default function App() {
  const auth = useAuth();
  const chat = useChat(() => auth.setAuthed(false));
  const [text, setText] = useState("");
  const [model, setModel] = useState<ModelId>("auto");
  const [effort, setEffort] = useState<Effort>("medium");
  const [mode, setMode] = useState<Mode>("chat");
  const [drawer, setDrawer] = useState(false);

  if (auth.authed === null) return <main className="h-full" />;
  if (!auth.authed) {
    return <LoginScreen error={auth.error} onSignIn={auth.signIn} onRegister={auth.registerDevice} />;
  }

  const submit = () => {
    const t = text;
    setText("");
    void chat.send(t);
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
    />
  );

  return (
    <div className="flex h-full bg-bg text-fg">
      <Sidebar
        recent={[]}
        onNew={chat.reset}
        userName="준"
        onLogout={() => auth.setAuthed(false)}
        open={drawer}
        onClose={() => setDrawer(false)}
      />
      <main className="min-w-0 flex-1">
        {chat.msgs.length === 0 ? (
          <Welcome>{composer}</Welcome>
        ) : (
          <ChatView
            msgs={chat.msgs}
            busy={chat.busy}
            notice={chat.notice}
            title="새 대화"
            modelLabel={MODEL_LABELS[model] ?? model}
            composer={composer}
            onMenu={() => setDrawer(true)}
          />
        )}
      </main>
    </div>
  );
}
