/** Shared contract between AssistantMessage/CodeBlock (producer) and ArtifactPanel (consumer). */
export type ArtifactData = {
  title: string;
  /** code fence language, e.g. "html", "svg", "tsx", "md" */
  lang: string;
  code: string;
};
