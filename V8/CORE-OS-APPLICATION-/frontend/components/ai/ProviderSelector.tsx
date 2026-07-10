"use client";

import { ChevronDown } from "lucide-react";
import { StatusDot } from "@/components/ui/StatusDot";
import type { AiProvider } from "@/types";

export function ProviderSelector({
  providers,
  value,
  onChange,
}: {
  providers: AiProvider[];
  value: string;
  onChange: (id: string) => void;
}) {
  const active = providers.find((p) => p.id === value);

  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-9 appearance-none rounded-md border border-border bg-surface-input pl-8 pr-8 text-[13px] text-content focus:border-primary/70 focus:outline-none"
          aria-label="AI provider"
        >
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
              {p.external ? " · external" : " · local"}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2">
          <StatusDot status={active?.status ?? "not_configured"} />
        </span>
        <ChevronDown size={14} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-content-subtle" />
      </div>
    </div>
  );
}
