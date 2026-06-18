"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { AlertTriangle, Info, MessageSquareText } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";

type DialogTone = "default" | "danger";

type BaseOptions = {
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: DialogTone;
};

type PromptOptions = BaseOptions & {
  defaultValue?: string;
  placeholder?: string;
};

type DialogRequest =
  | (BaseOptions & { kind: "alert"; resolve: () => void })
  | (BaseOptions & { kind: "confirm"; resolve: (value: boolean) => void })
  | (PromptOptions & { kind: "prompt"; resolve: (value: string | null) => void });

interface AppDialogValue {
  alert: (options: string | BaseOptions) => Promise<void>;
  confirm: (options: string | BaseOptions) => Promise<boolean>;
  prompt: (options: PromptOptions) => Promise<string | null>;
}

const AppDialogContext = createContext<AppDialogValue | null>(null);

function normalizeOptions(options: string | BaseOptions): BaseOptions {
  return typeof options === "string" ? { title: options } : options;
}

export function AppDialogProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<DialogRequest | null>(null);
  const [draft, setDraft] = useState("");

  const close = useCallback(() => setRequest(null), []);

  const alert = useCallback((options: string | BaseOptions) => {
    const base = normalizeOptions(options);
    return new Promise<void>((resolve) => {
      setDraft("");
      setRequest({ ...base, kind: "alert", resolve });
    });
  }, []);

  const confirm = useCallback((options: string | BaseOptions) => {
    const base = normalizeOptions(options);
    return new Promise<boolean>((resolve) => {
      setDraft("");
      setRequest({ ...base, kind: "confirm", resolve });
    });
  }, []);

  const prompt = useCallback((options: PromptOptions) => (
    new Promise<string | null>((resolve) => {
      setDraft(options.defaultValue ?? "");
      setRequest({ ...options, kind: "prompt", resolve });
    })
  ), []);

  const value = useMemo<AppDialogValue>(() => ({ alert, confirm, prompt }), [alert, confirm, prompt]);

  const cancel = () => {
    if (!request) return;
    if (request.kind === "alert") request.resolve();
    if (request.kind === "confirm") request.resolve(false);
    if (request.kind === "prompt") request.resolve(null);
    close();
  };

  const accept = () => {
    if (!request) return;
    if (request.kind === "alert") request.resolve();
    if (request.kind === "confirm") request.resolve(true);
    if (request.kind === "prompt") request.resolve(draft);
    close();
  };

  const Icon = request?.tone === "danger" ? AlertTriangle : request?.kind === "prompt" ? MessageSquareText : Info;

  return (
    <AppDialogContext.Provider value={value}>
      {children}
      <Modal
        open={Boolean(request)}
        onClose={cancel}
        title={
          <span className="flex items-center gap-2">
            <span className={request?.tone === "danger" ? "text-danger" : "text-primary"}>
              <Icon size={16} />
            </span>
            {request?.title ?? "AllHaven"}
          </span>
        }
        description={request?.kind === "prompt" ? request?.message : undefined}
        footer={
          <>
            {request?.kind !== "alert" ? (
              <Button variant="ghost" size="sm" onClick={cancel}>
                {request?.cancelLabel ?? "Cancel"}
              </Button>
            ) : null}
            <Button
              variant={request?.tone === "danger" ? "danger" : "primary"}
              size="sm"
              onClick={accept}
            >
              {request?.confirmLabel ?? (request?.kind === "alert" ? "OK" : "Confirm")}
            </Button>
          </>
        }
      >
        {request?.kind === "prompt" ? (
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") accept();
            }}
            placeholder={request.placeholder}
            className="h-11 w-full rounded-lg border border-border bg-surface-input px-3 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
          />
        ) : request?.message ? (
          <p className="text-sm leading-relaxed text-content-muted">{request.message}</p>
        ) : (
          <p className="text-sm text-content-muted">Please confirm to continue.</p>
        )}
      </Modal>
    </AppDialogContext.Provider>
  );
}

export function useAppDialog() {
  const ctx = useContext(AppDialogContext);
  if (!ctx) throw new Error("useAppDialog must be used inside AppDialogProvider");
  return ctx;
}
