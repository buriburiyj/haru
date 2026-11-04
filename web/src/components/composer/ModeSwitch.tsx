import type { Mode } from "../../types";
import { Tabs } from "../ui";

const OPTIONS: { id: Mode; label: string }[] = [
  { id: "chat", label: "채팅" },
  { id: "work", label: "Work" },
];

export default function ModeSwitch({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return <Tabs value={mode} options={OPTIONS} onChange={onChange} label="모드" />;
}
