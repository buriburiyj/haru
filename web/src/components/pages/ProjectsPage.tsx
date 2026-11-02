import PageShell from "./PageShell";

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
        <button
          type="button"
          onClick={onCreate}
          className="min-h-11 rounded-lg bg-accent px-4 py-3 text-sm font-medium text-accent-fg"
        >
          새 프로젝트
        </button>
      }
    >
      {demo ? (
        <ul className="space-y-3">
          {SAMPLE_PROJECTS.map((p) => (
            <li key={p.name} className="rounded-xl border border-line bg-surface p-4">
              <div className="font-medium">{p.name}</div>
              <div className="mt-1 text-sm text-muted">{p.goal}</div>
              <div className="mt-2 text-xs text-muted">{p.folder}</div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="max-w-sm text-sm text-muted">
            프로젝트마다 파일과 기억을 따로 보관해요. 다른 프로젝트의 내용과 섞이지 않아요.
          </p>
          <button
            type="button"
            onClick={onCreate}
            className="min-h-11 rounded-lg bg-accent px-5 py-3 text-sm font-medium text-accent-fg"
          >
            프로젝트 만들기
          </button>
        </div>
      )}
    </PageShell>
  );
}
