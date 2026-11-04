import type { ReactNode } from "react";
import type { ArtifactData } from "../artifact/types";
import CodeBlock from "./CodeBlock";

const INLINE_RE = /(`[^`\n]+`)|(\*\*[^*\n]+?\*\*)|(\*[^*\s][^*\n]*?\*)|(\[[^\]\n]+\]\([^)\s]+\))/;
const HR_RE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const UL_RE = /^\s*[-*+]\s+(.*)$/;
const OL_RE = /^\s*\d+[.)]\s+(.*)$/;
const FENCE_RE = /^\s*```\s*([^\s`]*)/;
const HEADING_RE = /^(#{1,6})\s+(.*)$/;
const TABLE_SEP_RE = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;

function inline(text: string, key = "i"): ReactNode[] {
  const out: ReactNode[] = [];
  let rest = text;
  let n = 0;
  while (rest) {
    const m = INLINE_RE.exec(rest);
    if (!m) {
      out.push(rest);
      break;
    }
    if (m.index > 0) out.push(rest.slice(0, m.index));
    const k = `${key}-${n++}`;
    const tok = m[0];
    if (m[1]) {
      out.push(
        <code key={k} className="rounded-control bg-surface-2 px-1 py-0.5 font-mono text-sm">
          {tok.slice(1, -1)}
        </code>,
      );
    } else if (m[2]) {
      out.push(<strong key={k}>{inline(tok.slice(2, -2), k)}</strong>);
    } else if (m[3]) {
      out.push(<em key={k}>{inline(tok.slice(1, -1), k)}</em>);
    } else {
      const lm = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(tok);
      if (lm && /^(https?:\/\/|mailto:)/i.test(lm[2])) {
        out.push(
          <a key={k} href={lm[2]} target="_blank" rel="noreferrer noopener" className="text-accent underline">
            {lm[1]}
          </a>,
        );
      } else {
        out.push(tok);
      }
    }
    rest = rest.slice(m.index + tok.length);
  }
  return out;
}

function splitRow(line: string): string[] {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split("|").map((c) => c.trim());
}

function isBlockStart(line: string, next?: string): boolean {
  return (
    FENCE_RE.test(line) ||
    HEADING_RE.test(line) ||
    HR_RE.test(line) ||
    /^\s*>/.test(line) ||
    UL_RE.test(line) ||
    OL_RE.test(line) ||
    (line.includes("|") && next !== undefined && TABLE_SEP_RE.test(next) && next.includes("-"))
  );
}

const HEADING_CLS = ["text-2xl", "text-xl", "text-lg", "text-base", "text-base", "text-sm"];

function parseBlocks(src: string, onOpenArtifact?: (a: ArtifactData) => void): ReactNode[] {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const key = `b${i}`;
    if (!line.trim()) {
      i++;
      continue;
    }
    const f = FENCE_RE.exec(line);
    if (f) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) buf.push(lines[i++]);
      i++; // closing fence (or end of streamed text)
      out.push(<CodeBlock key={key} lang={f[1]} code={buf.join("\n")} onOpenArtifact={onOpenArtifact} />);
      continue;
    }
    const h = HEADING_RE.exec(line);
    if (h) {
      out.push(
        <div key={key} role="heading" aria-level={h[1].length} className={`mt-3 mb-1 font-semibold ${HEADING_CLS[h[1].length - 1]}`}>
          {inline(h[2], key)}
        </div>,
      );
      i++;
      continue;
    }
    if (HR_RE.test(line)) {
      out.push(<hr key={key} className="my-3 border-line" />);
      i++;
      continue;
    }
    if (line.includes("|") && i + 1 < lines.length && lines[i + 1].includes("-") && TABLE_SEP_RE.test(lines[i + 1])) {
      const head = splitRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim() && lines[i].includes("|")) rows.push(splitRow(lines[i++]));
      out.push(
        <div key={key} className="my-2 max-w-full overflow-x-auto">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr>
                {head.map((c, ci) => (
                  <th key={ci} className="border border-line bg-surface-2 px-2 py-1 text-left font-semibold">
                    {inline(c, `${key}h${ci}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri}>
                  {head.map((_, ci) => (
                    <td key={ci} className="border border-line px-2 py-1">
                      {inline(r[ci] ?? "", `${key}r${ri}c${ci}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (/^\s*>/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
      out.push(
        <blockquote key={key} className="my-2 border-l-2 border-line pl-3 text-muted">
          {parseBlocks(buf.join("\n"), onOpenArtifact)}
        </blockquote>,
      );
      continue;
    }
    const isUl = UL_RE.test(line);
    if (isUl || OL_RE.test(line)) {
      const re = isUl ? UL_RE : OL_RE;
      const items: string[] = [];
      while (i < lines.length) {
        const m = re.exec(lines[i]);
        if (m) items.push(m[1]);
        else if (lines[i].trim() && /^\s{2,}/.test(lines[i]) && items.length && !UL_RE.test(lines[i]) && !OL_RE.test(lines[i]))
          items[items.length - 1] += " " + lines[i].trim();
        else break;
        i++;
      }
      const lis = items.map((t, li) => <li key={li}>{inline(t, `${key}l${li}`)}</li>);
      out.push(
        isUl ? (
          <ul key={key} className="my-2 list-disc pl-5">
            {lis}
          </ul>
        ) : (
          <ol key={key} className="my-2 list-decimal pl-5">
            {lis}
          </ol>
        ),
      );
      continue;
    }
    const buf: string[] = [line];
    i++;
    while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i], lines[i + 1])) buf.push(lines[i++]);
    out.push(
      <p key={key} className="my-2">
        {buf.flatMap((l, bi) => (bi === 0 ? inline(l, `${key}p0`) : [<br key={`br${bi}`} />, ...inline(l, `${key}p${bi}`)]))}
      </p>,
    );
  }
  return out;
}

export default function Markdown({ text, onOpenArtifact }: { text: string; onOpenArtifact?: (a: ArtifactData) => void }) {
  return <div className="max-w-full break-words text-fg">{parseBlocks(text, onOpenArtifact)}</div>;
}
