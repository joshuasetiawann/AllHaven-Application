"use client";

import { useEffect, useRef, useState } from "react";
import { Brain, Check, ChevronDown, Eraser, FolderGit2, Trash2 } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { useAppDialog } from "@/components/ui/AppDialog";
import { SECTIONS, projectSectionKey, resolveSection } from "@/lib/sections";
import {
  clearAllMemories,
  clearSection,
  getMemory,
  hasMemory,
  upsertMemory,
} from "@/lib/sectionMemory";
import { cn } from "@/lib/format";
import type { ChatGroup } from "@/types";

/**
 * Compact bar for the chat header: pick the active "section" (each carries its
 * own local memory) and view/edit/clear that section's memory. The chat injects
 * the active section's memory into prompts so answers stay relevant.
 */
export function SectionMemoryBar({
  sectionKey,
  onSectionChange,
  onMemoryChange,
  groups = [],
}: {
  sectionKey: string;
  onSectionChange: (key: string) => void;
  onMemoryChange?: () => void;
  groups?: ChatGroup[];
}) {
  const dialog = useAppDialog();
  const [menuOpen, setMenuOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [version, setVersion] = useState(0); // bump to re-read memory after edits
  const menuRef = useRef<HTMLDivElement>(null);

  const section = resolveSection(sectionKey, groups);
  const SectionIcon = section.icon;
  const present = hasMemory(sectionKey);
  const memory = getMemory(sectionKey);
  const bulletCount = memory?.important_context.length ?? 0;

  // editor draft
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [contextText, setContextText] = useState("");

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const openEditor = () => {
    const m = getMemory(sectionKey);
    setTitle(m?.title ?? "");
    setSummary(m?.summary ?? "");
    setContextText((m?.important_context ?? []).join("\n"));
    setEditOpen(true);
  };

  const notify = () => {
    setVersion((v) => v + 1);
    onMemoryChange?.();
  };

  const save = () => {
    upsertMemory(sectionKey, {
      title: title.trim(),
      summary: summary.trim(),
      important_context: contextText.split("\n").map((l) => l.trim()).filter(Boolean),
    });
    notify();
    setEditOpen(false);
  };

  const clearThis = () => {
    clearSection(sectionKey);
    setTitle("");
    setSummary("");
    setContextText("");
    notify();
  };

  const clearAll = async () => {
    const ok = await dialog.confirm({
      title: "Clear all local section memory?",
      message: "This removes all locally saved section memory on this device. This cannot be undone.",
      confirmLabel: "Clear all",
      tone: "danger",
    });
    if (!ok) return;
    clearAllMemories();
    notify();
    setEditOpen(false);
  };

  const inputCls =
    "w-full rounded-lg border border-border bg-surface-input px-3 py-2 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30";

  return (
    <>
      <div className="flex shrink-0 items-center gap-1.5">
        {/* Section selector */}
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-white/[0.03] px-2.5 py-1.5 text-[12px] text-content transition-colors hover:border-border-strong focus-ring"
            title="Active section — each keeps its own local memory"
          >
            <SectionIcon size={13} className="text-primary-bright" />
            <span className="max-w-[120px] truncate">{section.label}</span>
            <ChevronDown size={13} className="text-content-subtle" />
          </button>
          {menuOpen ? (
            <div className="absolute left-0 top-10 z-40 max-h-80 w-60 origin-top animate-pop overflow-y-auto rounded-xl border border-border bg-bg-deep/95 p-1.5 shadow-panel backdrop-blur-md">
              <p className="px-2 py-1.5 label-mono">Chat section</p>
              {SECTIONS.map((s) => {
                const Icon = s.icon;
                const active = s.key === sectionKey;
                const filled = hasMemory(s.key);
                return (
                  <button
                    key={s.key}
                    type="button"
                    onClick={() => {
                      onSectionChange(s.key);
                      setMenuOpen(false);
                    }}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left text-[13px] transition-colors",
                      active ? "bg-surface-high text-content" : "text-content-muted hover:bg-surface-raised/70 hover:text-content",
                    )}
                  >
                    <Icon size={15} className={cn("shrink-0", active ? "text-primary" : "text-content-subtle")} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{s.label}</span>
                      <span className="block truncate text-[10.5px] text-content-subtle">{s.hint}</span>
                    </span>
                    {filled ? <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" title="Has memory" /> : null}
                    {active ? <Check size={14} className="shrink-0 text-primary" /> : null}
                  </button>
                );
              })}

              {groups.length ? (
                <>
                  <p className="px-2 pb-1 pt-2 label-mono">Projects / Groups</p>
                  {groups.map((g) => {
                    const key = projectSectionKey(g.id);
                    const active = key === sectionKey;
                    const filled = hasMemory(key);
                    return (
                      <button
                        key={g.id}
                        type="button"
                        onClick={() => {
                          onSectionChange(key);
                          setMenuOpen(false);
                        }}
                        className={cn(
                          "flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left text-[13px] transition-colors",
                          active ? "bg-surface-high text-content" : "text-content-muted hover:bg-surface-raised/70 hover:text-content",
                        )}
                      >
                        <FolderGit2 size={15} className={cn("shrink-0", active ? "text-primary" : "text-content-subtle")} />
                        <span className="min-w-0 flex-1 truncate">{g.name}</span>
                        {filled ? <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" title="Has memory" /> : null}
                        {active ? <Check size={14} className="shrink-0 text-primary" /> : null}
                      </button>
                    );
                  })}
                </>
              ) : null}
            </div>
          ) : null}
        </div>

        {/* Memory chip / editor trigger */}
        <button
          type="button"
          onClick={openEditor}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-[12px] transition-colors focus-ring",
            present
              ? "border-secondary/30 bg-secondary/10 text-secondary-soft hover:bg-secondary/15"
              : "border-border bg-white/[0.03] text-content-muted hover:border-border-strong hover:text-content",
          )}
          title="View or edit this section's memory"
          data-version={version}
        >
          <Brain size={13} />
          <span className="hidden sm:inline">{present ? `Memory · ${bulletCount || "saved"}` : "Add memory"}</span>
        </button>
      </div>

      <Modal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title={
          <span className="flex items-center gap-2">
            <SectionIcon size={16} className="text-primary" /> {section.label} memory
          </span>
        }
        description="Local-only context the AI uses for this section. Never store secrets or API keys — credential-like text is masked automatically."
        footer={
          <>
            <Button variant="danger" size="sm" onClick={clearAll} className="mr-auto">
              <Trash2 size={14} /> Clear all
            </Button>
            <Button variant="ghost" size="sm" onClick={clearThis} disabled={!present}>
              <Eraser size={14} /> Clear this section
            </Button>
            <Button size="sm" onClick={save}>
              <Check size={14} /> Save
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="mb-1 block label-mono">Topic</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={80}
              placeholder={`e.g. ${section.label} working context`}
              className={inputCls}
            />
          </div>
          <div>
            <label className="mb-1 block label-mono">Summary</label>
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={3}
              maxLength={600}
              placeholder={section.hint}
              className={cn(inputCls, "resize-none")}
            />
          </div>
          <div>
            <label className="mb-1 block label-mono">Important context — one per line</label>
            <textarea
              value={contextText}
              onChange={(e) => setContextText(e.target.value)}
              rows={5}
              placeholder={"Prefers IDR currency\nBudget category names: Rent, Food, Transport"}
              className={cn(inputCls, "resize-none font-mono text-[12.5px]")}
            />
            <p className="mt-1 text-[11px] text-content-subtle">
              Up to 12 lines are kept. This is injected into the AI prompt only when relevant.
            </p>
          </div>
        </div>
      </Modal>
    </>
  );
}
