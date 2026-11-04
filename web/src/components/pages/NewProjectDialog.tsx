import { useState } from "react";
import { Button, Dialog, Input, Textarea } from "../ui";

export default function NewProjectDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [folder, setFolder] = useState("");

  return (
    <Dialog
      title="새 프로젝트"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            취소
          </Button>
          <Button variant="primary" type="submit" form="new-project-form" disabled={!name.trim()}>
            만들기
          </Button>
        </>
      }
    >
      <form
        id="new-project-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) onClose();
        }}
        className="space-y-4"
      >
        <label className="block space-y-1">
          <span className="text-sm text-muted">이름</span>
          <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </label>
        <label className="block space-y-1">
          <span className="text-sm text-muted">목표</span>
          <Textarea rows={4} value={goal} onChange={(e) => setGoal(e.target.value)} />
        </label>
        <label className="block space-y-1">
          <span className="text-sm text-muted">폴더 연결</span>
          <Input value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="jun-files/projects/…" />
          <span className="block text-xs text-muted">폴더는 jun-files 저장소 안에 만들어져요.</span>
        </label>
      </form>
    </Dialog>
  );
}
