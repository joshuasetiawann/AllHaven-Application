"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CornerDownLeft, FileText, LayoutGrid, ListChecks, Search } from "lucide-react";
import { MODULE_NAV, PRIMARY_NAV, SETTINGS_NAV } from "@/components/layout/nav";
import { notesApi, tasksApi } from "@/lib/api";
import { cn } from "@/lib/format";

interface Item {
  id: string;
  type: "nav" | "task" | "note";
  label: string;
  href: string;
  hint?: string;
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [active, setActive] = useState(0);

  const navItems: Item[] = useMemo(
    () =>
      [...PRIMARY_NAV, ...MODULE_NAV, SETTINGS_NAV].map((n) => ({
        id: `nav-${n.href}`,
        type: "nav" as const,
        label: n.label,
        href: n.href,
        hint: "Go to",
      })),
    [],
  );

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    Promise.all([tasksApi.list().catch(() => []), notesApi.list().catch(() => [])]).then(
      ([tasks, notes]) => {
        setItems([
          ...tasks.slice(0, 30).map((t) => ({
            id: `task-${t.id}`,
            type: "task" as const,
            label: t.title,
            href: "/dashboard/tasks",
            hint: "Task",
          })),
          ...notes.slice(0, 30).map((n) => ({
            id: `note-${n.id}`,
            type: "note" as const,
            label: n.title,
            href: "/dashboard/notes",
            hint: "Note",
          })),
        ]);
      },
    );
  }, [open]);

  const results = useMemo(() => {
    const all = [...navItems, ...items];
    const q = query.trim().toLowerCase();
    const filtered = q ? all.filter((i) => i.label.toLowerCase().includes(q)) : all;
    return filtered.slice(0, 24);
  }, [navItems, items, query]);

  useEffect(() => setActive(0), [query]);

  if (!open) return null;

  const go = (item: Item) => {
    router.push(item.href);
    onClose();
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      go(results[active]);
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  const iconFor = (t: Item["type"]) =>
    t === "task" ? <ListChecks size={15} /> : t === "note" ? <FileText size={15} /> : <LayoutGrid size={15} />;

  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center p-3 pt-[10vh] sm:p-4 sm:pt-[12vh]">
      <div className="absolute inset-0 bg-black/65 backdrop-blur-sm" onClick={onClose} aria-hidden />
      <div className="relative z-10 w-full max-w-2xl animate-scale-in overflow-hidden rounded-2xl border border-border bg-surface/95 shadow-glow">
        <div className="flex items-center gap-2.5 border-b border-border bg-surface-input/35 px-4">
          <Search size={16} className="text-content-subtle" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder="Search tasks, notes, pages…"
            className="h-12 flex-1 bg-transparent text-sm text-content placeholder:text-content-subtle focus:outline-none"
          />
          <kbd className="rounded-md border border-border bg-surface-high px-1.5 py-0.5 text-[10px] text-content-subtle">ESC</kbd>
        </div>
        <ul className="custom-scrollbar max-h-[56vh] overflow-y-auto p-2">
          {results.length === 0 ? (
            <li className="px-3 py-6 text-center text-[13px] text-content-muted">No matches.</li>
          ) : (
            results.map((item, i) => (
              <li key={item.id}>
                <button
                  onMouseEnter={() => setActive(i)}
                  onClick={() => go(item)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-left text-sm transition-colors",
                    i === active
                      ? "border-primary/25 bg-primary/10 text-content"
                      : "border-transparent text-content-muted hover:border-border hover:bg-surface-raised/60",
                  )}
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-content-subtle">
                      {iconFor(item.type)}
                    </span>
                    <span className="truncate">{item.label}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="text-[11px] text-content-subtle">{item.hint}</span>
                    {i === active ? <CornerDownLeft size={13} className="text-primary" /> : null}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
