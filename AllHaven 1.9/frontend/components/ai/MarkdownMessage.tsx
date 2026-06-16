"use client";

import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/format";

// A small, dependency-free Markdown renderer for AI chat output. It covers the
// common cases models emit — headings, paragraphs, bold/italic/inline-code,
// fenced code blocks, blockquotes, ordered/unordered lists, and links — so
// responses read cleanly instead of as one raw, run-on blob. It never uses
// dangerouslySetInnerHTML, so there is no HTML-injection risk.

const INLINE_RE = /(`[^`]+`)|(\*\*[^*]+\*\*|__[^_]+__)|(\*[^*\s][^*]*\*|_[^_\s][^_]*_)|(\[[^\]]+\]\([^)\s]+\))/;

function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let rest = text;
  let k = 0;
  while (rest.length) {
    const m = INLINE_RE.exec(rest);
    if (!m) {
      nodes.push(<Fragment key={k++}>{rest}</Fragment>);
      break;
    }
    if (m.index > 0) nodes.push(<Fragment key={k++}>{rest.slice(0, m.index)}</Fragment>);
    const tok = m[0];
    if (tok.startsWith("`")) {
      nodes.push(
        <code key={k++} className="rounded bg-black/30 px-1 py-0.5 font-mono text-[0.85em] text-content">
          {tok.slice(1, -1)}
        </code>,
      );
    } else if (tok.startsWith("**") || tok.startsWith("__")) {
      nodes.push(<strong key={k++} className="font-semibold text-content">{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("*") || tok.startsWith("_")) {
      nodes.push(<em key={k++}>{tok.slice(1, -1)}</em>);
    } else {
      const link = /\[([^\]]+)\]\(([^)\s]+)\)/.exec(tok);
      if (link) {
        nodes.push(
          <a key={k++} href={link[2]} target="_blank" rel="noreferrer" className="text-primary underline underline-offset-2 hover:text-primary-bright">
            {link[1]}
          </a>,
        );
      } else {
        nodes.push(<Fragment key={k++}>{tok}</Fragment>);
      }
    }
    rest = rest.slice(m.index + tok.length);
  }
  return nodes;
}

const HEADING_SIZES = ["text-[15px]", "text-[15px]", "text-[14px]", "text-[13.5px]", "text-[13px]", "text-[13px]"];

export function MarkdownMessage({ content, className }: { content: string; className?: string }) {
  const lines = (content || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    const fence = /^```(\w*)\s*$/.exec(line);
    if (fence) {
      const buf: string[] = [];
      i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) { buf.push(lines[i]); i += 1; }
      i += 1; // closing fence
      blocks.push(
        <pre key={key++} className="custom-scrollbar overflow-x-auto rounded-lg border border-border bg-black/40 p-3 text-[12px] leading-relaxed">
          <code className="font-mono text-content">{buf.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // Blank line
    if (/^\s*$/.test(line)) { i += 1; continue; }

    // Horizontal rule
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { blocks.push(<hr key={key++} className="my-2 border-border" />); i += 1; continue; }

    // Heading
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      blocks.push(
        <p key={key++} className={cn("mt-1 font-semibold text-content", HEADING_SIZES[level - 1])}>
          {renderInline(heading[2])}
        </p>,
      );
      i += 1;
      continue;
    }

    // Blockquote
    if (/^\s*>\s?/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^\s*>\s?/, "")); i += 1; }
      blocks.push(
        <blockquote key={key++} className="border-l-2 border-primary/40 pl-3 text-content-muted">
          {renderInline(buf.join(" "))}
        </blockquote>,
      );
      continue;
    }

    // Lists (group consecutive list items; ordered if the first is numbered)
    if (/^\s*([-*+]\s+|\d+[.)]\s+)/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*([-*+]\s+|\d+[.)]\s+)/.test(lines[i])) {
        const item = lines[i].replace(/^\s*([-*+]\s+|\d+[.)]\s+)/, "");
        items.push(<li key={items.length}>{renderInline(item)}</li>);
        i += 1;
      }
      blocks.push(
        ordered
          ? <ol key={key++} className="list-decimal space-y-0.5 pl-5">{items}</ol>
          : <ul key={key++} className="list-disc space-y-0.5 pl-5">{items}</ul>,
      );
      continue;
    }

    // Paragraph: gather consecutive plain lines
    const buf: string[] = [];
    while (
      i < lines.length && !/^\s*$/.test(lines[i]) && !/^```/.test(lines[i]) &&
      !/^(#{1,6})\s+/.test(lines[i]) && !/^\s*>\s?/.test(lines[i]) &&
      !/^\s*([-*+]\s+|\d+[.)]\s+)/.test(lines[i]) && !/^\s*([-*_])(\s*\1){2,}\s*$/.test(lines[i])
    ) {
      buf.push(lines[i]);
      i += 1;
    }
    blocks.push(
      <p key={key++} className="break-words">
        {buf.map((b, idx) => (
          <Fragment key={idx}>
            {idx > 0 ? <br /> : null}
            {renderInline(b)}
          </Fragment>
        ))}
      </p>,
    );
  }

  return <div className={cn("space-y-2 leading-relaxed", className)}>{blocks}</div>;
}
