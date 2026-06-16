"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, Menu, Search, Settings as SettingsIcon } from "lucide-react";
import { Avatar } from "@/components/ui/Avatar";
import { IconButton } from "@/components/ui/IconButton";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { aiApi } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { cn, initials } from "@/lib/format";
import type { ToolProposal } from "@/types";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const router = useRouter();
  const user = getStoredUser();
  // Reflects the real local AI *provider* (Ollama) status — online only after a
  // successful Test Connection, configured if set up, else not configured.
  const [aiStatus, setAiStatus] = useState<"online" | "configured" | "not_configured" | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [proposals, setProposals] = useState<ToolProposal[]>([]);
  const notifRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    aiApi
      .listProviders()
      .then((res) => {
        if (!active) return;
        const ollama = res.providers.find((p) => p.id === "ollama");
        const s = ollama?.status;
        setAiStatus(s === "online" ? "online" : ollama?.configured ? "configured" : "not_configured");
      })
      .catch(() => active && setAiStatus("not_configured"));
    const loadProposals = () => {
      aiApi
        .listProposals()
        .then((p) => active && setProposals(p))
        .catch(() => {});
    };
    loadProposals();
    const interval = window.setInterval(loadProposals, 30000);
    return () => {
      active = false;
      window.clearInterval(interval);
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

  const statusLabel =
    aiStatus === null
      ? "Checking"
      : aiStatus === "online"
        ? "Online"
        : aiStatus === "configured"
          ? "Configured"
          : "Not configured";

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 min-w-0 items-center gap-2 border-b border-border/80 bg-bg/80 px-3 shadow-[0_1px_0_rgba(255,255,255,0.02)] backdrop-blur-[14px] sm:h-16 sm:gap-3 sm:px-6">
        <IconButton className="shrink-0 md:hidden" onClick={onMenu} aria-label="Open menu">
          <Menu size={18} />
        </IconButton>

        <button
          onClick={() => setPaletteOpen(true)}
          className="flex h-10 min-w-0 flex-1 items-center gap-2 rounded-xl border border-border bg-surface-input/70 px-3 text-left text-content-subtle shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] transition-all duration-200 hover:border-primary/35 hover:bg-surface-input sm:max-w-lg xl:max-w-2xl"
        >
          <Search size={15} className="shrink-0" />
          <span className="min-w-0 flex-1 truncate text-[13px] sm:hidden">Search</span>
          <span className="hidden min-w-0 flex-1 truncate text-[13px] sm:block">Search tasks, notes, pages…</span>
          <kbd className="hidden shrink-0 rounded border border-border px-1.5 py-0.5 text-[10px] sm:inline">⌘K</kbd>
        </button>

        <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
          <span
            className={cn(
              "hidden max-w-[220px] items-center gap-2 truncate rounded-full border px-3 py-1.5 text-[12px] font-medium lg:inline-flex",
              aiStatus === "online"
                ? "border-success/30 bg-success/10 text-success"
                : aiStatus === "configured"
                  ? "border-primary/30 bg-primary/10 text-primary"
                  : "border-border bg-surface-high/80 text-content-muted",
            )}
          >
            <span
              className={cn(
                "h-1.5 w-1.5 shrink-0 rounded-full",
                aiStatus === "online" ? "bg-success" : aiStatus === "configured" ? "bg-primary" : "bg-content-subtle",
              )}
            />
            <span className="truncate">Local AI · {statusLabel}</span>
          </span>
          <div className="flex shrink-0 items-center gap-1 sm:gap-2">
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
                <div className="absolute right-0 top-11 z-40 w-[min(92vw,22rem)] animate-scale-in rounded-2xl border border-border bg-surface p-2 shadow-glow">
                  <div className="flex items-center justify-between gap-3 px-2 py-1.5">
                    <div>
                      <p className="text-[13px] font-semibold text-content">Approvals</p>
                      <p className="text-[11.5px] text-content-subtle">
                        {proposals.length ? `${proposals.length} action${proposals.length === 1 ? "" : "s"} waiting` : "Nothing waiting"}
                      </p>
                    </div>
                    <span className="rounded-full border border-border bg-surface-input px-2 py-0.5 text-[10px] uppercase tracking-wide text-content-subtle">
                      AI
                    </span>
                  </div>
                  {proposals.length === 0 ? (
                    <p className="mx-1 rounded-xl border border-border/70 bg-surface-input/45 px-3 py-3 text-[13px] text-content-muted">
                      You&apos;re all caught up.
                    </p>
                  ) : (
                    <ul className="mt-1 space-y-1">
                      {proposals.slice(0, 5).map((p) => (
                        <li key={p.id}>
                          <button
                            onClick={() => {
                              setNotifOpen(false);
                              router.push("/dashboard/approvals");
                            }}
                            className="flex w-full items-center justify-between gap-2 rounded-xl px-2.5 py-2 text-left text-[13px] text-content transition-colors hover:bg-surface-raised/70"
                          >
                            <span className="min-w-0">
                              <span className="block truncate font-medium">{p.tool_name.replace(/_/g, " ")}</span>
                              <span className="block text-[11px] text-content-subtle">Needs your decision</span>
                            </span>
                            <span
                              className={cn(
                                "shrink-0 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide",
                                p.risk_level === "HIGH"
                                  ? "border-danger/30 bg-danger/10 text-danger"
                                  : p.risk_level === "MEDIUM"
                                    ? "border-warning/30 bg-warning/10 text-warning"
                                    : "border-border bg-surface-high text-content-subtle",
                              )}
                            >
                              {p.risk_level}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <Link
                    href="/dashboard/approvals"
                    onClick={() => setNotifOpen(false)}
                    className="mt-1 flex items-center justify-center rounded-xl border border-border bg-surface-input/55 px-3 py-2 text-[13px] font-medium text-primary transition-colors hover:border-primary/40 hover:bg-primary/10"
                  >
                    Open approvals
                  </Link>
                </div>
              ) : null}
            </div>

            <Link href="/dashboard/settings" aria-label="Settings">
              <IconButton aria-label="Settings">
                <SettingsIcon size={17} />
              </IconButton>
            </Link>
            <div
              title={user?.full_name || user?.email || "Account"}
              className="rounded-full border border-border bg-surface-input/45 p-0.5"
            >
              <Avatar initials={initials(user?.full_name || user?.email)} />
            </div>
          </div>
        </div>
      </header>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </>
  );
}
