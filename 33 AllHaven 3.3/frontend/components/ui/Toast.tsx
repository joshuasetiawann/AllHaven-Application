"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "@/lib/format";

type ToastTone = "success" | "danger" | "warning" | "info";

interface ToastInput {
  title: string;
  description?: string;
  tone?: ToastTone;
  durationMs?: number;
}

interface ToastItem extends ToastInput {
  id: string;
  tone: ToastTone;
}

interface ToastContextValue {
  notify: (toast: ToastInput) => string;
  success: (title: string, description?: string) => string;
  danger: (title: string, description?: string) => string;
  warning: (title: string, description?: string) => string;
  info: (title: string, description?: string) => string;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const toneStyles: Record<ToastTone, string> = {
  success: "border-success/30 bg-success/10 text-success",
  danger: "border-danger/30 bg-danger/10 text-danger",
  warning: "border-warning/35 bg-warning/10 text-warning",
  info: "border-info/30 bg-info/10 text-info",
};

const icons: Record<ToastTone, typeof CheckCircle2> = {
  success: CheckCircle2,
  danger: XCircle,
  warning: AlertTriangle,
  info: Info,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((cur) => cur.filter((item) => item.id !== id));
  }, []);

  const notify = useCallback((toast: ToastInput) => {
    const id = `toast-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const item: ToastItem = {
      id,
      title: toast.title,
      description: toast.description,
      tone: toast.tone ?? "info",
      durationMs: toast.durationMs ?? 4200,
    };
    setItems((cur) => [item, ...cur].slice(0, 5));
    if ((item.durationMs ?? 0) > 0) {
      window.setTimeout(() => dismiss(id), item.durationMs);
    }
    return id;
  }, [dismiss]);

  const value = useMemo<ToastContextValue>(() => ({
    notify,
    dismiss,
    success: (title, description) => notify({ title, description, tone: "success" }),
    danger: (title, description) => notify({ title, description, tone: "danger", durationMs: 6500 }),
    warning: (title, description) => notify({ title, description, tone: "warning", durationMs: 5500 }),
    info: (title, description) => notify({ title, description, tone: "info" }),
  }), [dismiss, notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-3 top-20 z-[80] flex w-[min(92vw,380px)] flex-col gap-2 sm:right-5">
        {items.map((item) => {
          const Icon = icons[item.tone];
          return (
            <div
              key={item.id}
              className={cn(
                "pointer-events-auto animate-slide-up rounded-xl border px-3 py-3 shadow-glow backdrop-blur-xl",
                "bg-surface/95",
                toneStyles[item.tone],
              )}
            >
              <div className="flex items-start gap-2.5">
                <Icon size={17} className="mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-semibold text-content">{item.title}</p>
                  {item.description ? (
                    <p className="mt-0.5 text-[12px] leading-relaxed text-content-muted">{item.description}</p>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(item.id)}
                  className="rounded-md p-1 text-content-subtle transition-colors hover:bg-surface-high hover:text-content"
                  aria-label="Dismiss notification"
                >
                  <X size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
