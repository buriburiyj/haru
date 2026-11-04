// Temporary sample data for the customize screens (replaced by the server in stage 2).
export type Kind = "skills" | "connectors" | "plugins";

export const KIND_LABEL: Record<Kind, string> = { skills: "Skills", connectors: "커넥터", plugins: "플러그인" };
export const KIND_NOUN: Record<Kind, string> = { skills: "스킬", connectors: "커넥터", plugins: "플러그인" };

export type SkillItem = { name: string; provider: string; description: string; date: string };
export type ConnectorItem = { name: string; description: string; type: "웹" | "로컬"; connected: boolean };
export type PluginItem = { name: string; description: string; includes: string };

export const MY_SKILLS: SkillItem[] = [
  { name: "skill-creator", provider: "기본 제공", description: "새 스킬을 만들고 고칩니다.", date: "2026-11-02" },
  { name: "morning", provider: "기본 제공", description: "아침 브리핑을 만들어 줍니다.", date: "2026-11-02" },
  { name: "import-memory", provider: "기본 제공", description: "다른 곳의 기억을 가져옵니다.", date: "2026-11-02" },
];

export const MY_CONNECTORS: ConnectorItem[] = [
  { name: "Gmail", description: "메일을 읽고 찾습니다.", type: "웹", connected: true },
  { name: "Filesystem", description: "맥의 폴더를 읽습니다.", type: "로컬", connected: true },
];

/** GitHub status is real (githubRepos()), so this row has no `connected` flag. */
export const GITHUB_CONNECTOR: Omit<ConnectorItem, "connected"> = { name: "GitHub", description: "저장소를 읽기 전용으로 봅니다.", type: "웹" };

export const MY_PLUGINS: PluginItem[] = [];

export const EXPLORE_SKILLS: SkillItem[] = [
  { name: "pdf", provider: "Anthropic", description: "PDF를 만들고 읽습니다.", date: "" },
  { name: "docx", provider: "Anthropic", description: "Word 문서를 만들고 고칩니다.", date: "" },
  { name: "xlsx", provider: "Anthropic", description: "Excel 표를 만들고 고칩니다.", date: "" },
];

export const EXPLORE_CONNECTORS: ConnectorItem[] = [
  { name: "Google 드라이브", description: "문서와 파일을 찾습니다.", type: "웹", connected: false },
  { name: "Notion", description: "페이지와 데이터베이스를 읽습니다.", type: "웹", connected: false },
  { name: "Gmail", description: "메일을 읽고 찾습니다.", type: "웹", connected: true },
];

export const EXPLORE_PLUGINS: PluginItem[] = [
  { name: "오피스 묶음", description: "문서 스킬과 드라이브 커넥터를 한 번에 설치합니다.", includes: "스킬 3 · 커넥터 1" },
];
