"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain, Clock } from "lucide-react";
import { memoryApi } from "@/lib/api";
import { cn } from "@/lib/format";

type IndicatorState = "idle" | "updated" | "pending";

interface MemoryIndicatorProps {
  /** Bump this counter after each AI response to trigger a refresh. */
  refreshKey: number;
  className?: string;
}

export function MemoryIndicator({ refreshKey, className }: MemoryIndicatorProps) {
  const [state, setState] = useState<IndicatorState>("idle");
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    if (refreshKey === 0) return;
    let active = true;
    // Show "updated" flash briefly, then check for pending suggestions.
    setState("updated");
    const timer = setTimeout(() => {
      memoryApi.listSuggestions()
        .then((s) => {
          if (!active) return;
          setPendingCount(s.length);
          setState(s.length > 0 ? "pending" : "idle");
        })
        .catch(() => {
          if (!active) return;
          setPendingCount(0);
          setState("idle");
        });
    }, 1500);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [refreshKey]);

  if (state === "idle" && pendingCount === 0) return null;

  return (
    <Link
      href="/dashboard/ai/memory"
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
        state === "updated"
          ? "border-success/30 bg-success/10 text-success"
          : "border-warning/30 bg-warning/10 text-warning",
        className,
      )}
    >
      {state === "updated" ? (
        <><Brain size={11} /> Memory updated</>
      ) : (
        <><Clock size={11} /> {pendingCount} {pendingCount === 1 ? "memory" : "memories"} pending</>
      )}
    </Link>
  );
}
