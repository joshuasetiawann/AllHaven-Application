"use client";

import { useState } from "react";
import { Eye, EyeOff, ShieldCheck } from "lucide-react";
import type { SecretPreview } from "@/types";

export function SecretInput({
  id,
  label,
  value,
  onChange,
  placeholder,
  existing,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  existing?: SecretPreview;
}) {
  const [show, setShow] = useState(false);
  const isSaved = Boolean(existing?.configured);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="block text-[12px] font-medium uppercase tracking-wide text-content-muted">
          {label}
        </label>
        {isSaved ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-success">
            <ShieldCheck size={12} /> Saved · {existing?.preview}
          </span>
        ) : null}
      </div>
      <div className="relative">
        <input
          id={id}
          type={show ? "text" : "password"}
          autoComplete="off"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={isSaved ? "Leave blank to keep current key" : placeholder || "Paste secret…"}
          className="h-10 w-full rounded-md border border-border bg-surface-input pl-3 pr-10 font-mono text-sm text-content placeholder:font-sans placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-content-subtle hover:text-content"
          aria-label={show ? "Hide" : "Show"}
        >
          {show ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </div>
  );
}
