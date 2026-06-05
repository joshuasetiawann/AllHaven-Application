"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell, Menu, Search, Settings as SettingsIcon } from "lucide-react";
import { Avatar } from "@/components/ui/Avatar";
import { IconButton } from "@/components/ui/IconButton";
import { settingsApi } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { cn, initials } from "@/lib/format";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const user = getStoredUser();
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);

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
    return () => {
      active = false;
    };
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-bg/80 px-4 backdrop-blur-[12px] sm:px-6">
      <IconButton className="lg:hidden" onClick={onMenu} aria-label="Open menu">
        <Menu size={18} />
      </IconButton>

      {/* Search (decorative in MVP — honest placeholder) */}
      <div className="hidden flex-1 items-center gap-2 sm:flex">
        <div className="flex h-9 w-full max-w-md items-center gap-2 rounded-md border border-border bg-surface-input px-3 text-content-subtle">
          <Search size={15} />
          <span className="text-[13px]">Search is not wired in this MVP</span>
        </div>
      </div>
      <div className="flex-1 sm:hidden" />

      {/* Honest local-AI status pill */}
      <span
        className={cn(
          "hidden items-center gap-2 rounded-full border px-3 py-1.5 text-[12px] font-medium sm:inline-flex",
          aiConfigured
            ? "border-primary/30 bg-primary/10 text-primary"
            : "border-border bg-surface-high text-content-muted",
        )}
      >
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            aiConfigured ? "bg-primary" : "bg-content-subtle",
          )}
        />
        Local AI · {aiConfigured === null ? "…" : aiConfigured ? "Connected" : "Not configured"}
      </span>

      <div className="flex items-center gap-2">
        <IconButton aria-label="Notifications" title="No notifications in MVP">
          <Bell size={17} />
        </IconButton>
        <Link href="/dashboard/settings" aria-label="Settings">
          <IconButton aria-label="Settings">
            <SettingsIcon size={17} />
          </IconButton>
        </Link>
        <Avatar initials={initials(user?.full_name || user?.email)} />
      </div>
    </header>
  );
}
