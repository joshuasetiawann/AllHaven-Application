"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/format";

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: "md" | "lg";
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) {
      document.addEventListener("keydown", handler);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-black/65 backdrop-blur-sm animate-fade-in" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative z-10 w-full animate-scale-in rounded-t-2xl border border-border bg-surface shadow-glow sm:rounded-2xl",
          size === "lg" ? "max-w-2xl" : "max-w-lg",
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            <h3 className="text-[15px] font-semibold text-content">{title}</h3>
            {description ? <p className="mt-0.5 text-[13px] text-content-muted">{description}</p> : null}
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-content-subtle transition-colors hover:bg-surface-high hover:text-content focus-ring"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>
        <div className="custom-scrollbar max-h-[70svh] overflow-y-auto px-4 py-4 sm:px-5">{children}</div>
        {footer ? (
          <div className="flex flex-wrap justify-end gap-2 border-t border-border px-4 py-4 sm:px-5">{footer}</div>
        ) : null}
      </div>
    </div>
  );
}
