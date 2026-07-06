"use client";

import { useEffect, useRef, useState } from "react";
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
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    if (refreshKey === 0) return;
    // Show "updated" flash briefly, then check for pending suggestions.
    setState("updated");
    const timer = setTimeout(() => {
      memoryApi.listSuggestions()
        .then((s) => {
          if (!mountedRef.current) return;
          setPendingCount(s.length);
          setState(s.length > 0 ? "pending" : "idle");
        })
        .catch(() => {
          if (mountedRef.current) setState("idle");
        });
    }, 1500);
    return () => clearTimeout(timer);
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
        <><Clock size={11} /> {pendingCount} memory pending</>
      )}
    </Link>
  );
}
