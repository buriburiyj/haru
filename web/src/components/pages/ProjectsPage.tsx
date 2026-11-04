import PageShell from "./PageShell";
import { Button, Card } from "../ui";

const SAMPLE_PROJECTS = [
  { name: "하루 앱", goal: "개인 AI 앱 만들기", folder: "jun-files/projects/haru" },
  { name: "독서 노트", goal: "읽은 책 정리와 요약", folder: "jun-files/projects/books" },
];

export default function ProjectsPage({ onClose, onCreate }: { onClose: () => void; onCreate: () => void }) {
  const demo = typeof window !== "undefined" && window.location.search.includes("demo=projects");
  return (
    <PageShell
      title="프로젝트"
      onClose={onClose}
      actions={
        <Button variant="primary" onClick={onCreate}>
          새 프로젝트
        </Button>
      }
    >
      {demo ? (
        <div className="space-y-3">
          {SAMPLE_PROJECTS.map((p) => (
            <Card key={p.name} className="list-none">
              <div className="font-medium">{p.name}</div>
              <div className="mt-1 text-sm text-muted">{p.goal}</div>
              <div className="mt-2 text-xs text-muted">{p.folder}</div>
            </Card>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="max-w-sm text-sm text-muted">
            프로젝트마다 파일과 기억을 따로 보관해요. 다른 프로젝트의 내용과 섞이지 않아요.
          </p>
          <Button variant="primary" onClick={onCreate}>
            프로젝트 만들기
          </Button>
        </div>
      )}
    </PageShell>
  );
}
