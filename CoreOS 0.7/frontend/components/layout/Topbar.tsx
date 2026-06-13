"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, Menu, Search, Settings as SettingsIcon } from "lucide-react";
import { Avatar } from "@/components/ui/Avatar";
import { IconButton } from "@/components/ui/IconButton";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { aiApi, settingsApi } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { cn, initials } from "@/lib/format";
import type { ToolProposal } from "@/types";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const router = useRouter();
  const user = getStoredUser();
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [proposals, setProposals] = useState<ToolProposal[]>([]);
  const notifRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    settingsApi
      .integrations()
      .then((res) => {
        if (!active) return;
        const ollama = res.integrations.find((i) => i.key === "ollama");
        setAiConfigured(Boolean(ollama?.configured));
      })
      .catch(() => active && setAiConfigured(false));
    aiApi
      .listProposals()
      .then((p) => active && setProposals(p))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  // Cmd/Ctrl-K opens the command palette.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Close the notifications popover on outside click.
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setNotifOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <>
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-bg/80 px-4 backdrop-blur-[12px] sm:px-6">
        <IconButton className="lg:hidden" onClick={onMenu} aria-label="Open menu">
          <Menu size={18} />
        </IconButton>

        {/* Working command palette trigger */}
        <button
          onClick={() => setPaletteOpen(true)}
          className="flex h-9 flex-1 items-center gap-2 rounded-md border border-border bg-surface-input px-3 text-left text-content-subtle transition-colors hover:border-border-strong sm:max-w-md"
        >
          <Search size={15} />
          <span className="flex-1 text-[13px]">Search tasks, notes, pages…</span>
          <kbd className="hidden rounded border border-border px-1.5 py-0.5 text-[10px] sm:inline">⌘K</kbd>
        </button>

        <span
          className={cn(
            "hidden items-center gap-2 rounded-full border px-3 py-1.5 text-[12px] font-medium sm:inline-flex",
            aiConfigured
              ? "border-primary/30 bg-primary/10 text-primary"
              : "border-border bg-surface-high text-content-muted",
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", aiConfigured ? "bg-primary" : "bg-content-subtle")} />
          Local AI · {aiConfigured === null ? "…" : aiConfigured ? "Connected" : "Not configured"}
        </span>

        <div className="flex items-center gap-2">
          <div className="relative" ref={notifRef}>
            <IconButton aria-label="Notifications" active={notifOpen} onClick={() => setNotifOpen((o) => !o)}>
              <Bell size={17} />
              {proposals.length > 0 ? (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[9px] font-semibold text-primary-fg">
                  {proposals.length}
                </span>
              ) : null}
            </IconButton>
            {notifOpen ? (
              <div className="absolute right-0 top-11 z-40 w-72 animate-scale-in rounded-xl border border-border bg-surface p-2 shadow-glow">
                <p className="px-2 py-1.5 font-mono text-[10px] uppercase tracking-wide text-content-subtle">
                  Pending AI proposals
                </p>
                {proposals.length === 0 ? (
                  <p className="px-2 py-3 text-[13px] text-content-muted">You&apos;re all caught up.</p>
                ) : (
                  <ul className="space-y-1">
                    {proposals.slice(0, 5).map((p) => (
                      <li key={p.id}>
                        <button
                          onClick={() => {
                            setNotifOpen(false);
                            router.push("/dashboard/ai");
                          }}
                          className="flex w-full items-center justify-between gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-content hover:bg-surface-raised/60"
                        >
                          <span className="truncate font-mono">{p.tool_name}</span>
                          <span className="text-[10px] uppercase text-content-subtle">{p.risk_level}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <Link
                  href="/dashboard/ai"
                  onClick={() => setNotifOpen(false)}
                  className="mt-1 block rounded-lg px-2 py-2 text-[13px] text-primary hover:bg-surface-raised/60"
                >
                  Open AI Chat →
                </Link>
              </div>
            ) : null}
          </div>

          <Link href="/dashboard/settings" aria-label="Settings">
            <IconButton aria-label="Settings">
              <SettingsIcon size={17} />
            </IconButton>
          </Link>
          <Avatar initials={initials(user?.full_name || user?.email)} />
        </div>
      </header>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </>
  );
}
