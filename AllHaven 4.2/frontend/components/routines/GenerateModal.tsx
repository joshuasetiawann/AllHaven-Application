import { useEffect, useState } from "react";
import { AlertTriangle, Settings2, Sparkles, Trash2, Wand2 } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { cn } from "@/lib/format";
import { ApiException, routinesApi } from "@/lib/api";
import type { RoutineDraft, RoutineGenerateStatus } from "@/types";
import {
  PERIODS,
  REPEAT_OPTIONS,
  type RepeatRule,
  type TimePeriod,
  isoToLocalInput,
} from "./shared";

type Phase = "prompt" | "loading" | "review" | "saving";

interface EditableDraft {
  title: string;
  start_at: string; // local "YYYY-MM-DDTHH:MM"
  end_at: string;
  location: string;
  description: string;
  all_day: boolean;
  time_period: TimePeriod;
  repeat_rule: RepeatRule;
  repeat_days: string[];
}

function toEditable(draft: RoutineDraft): EditableDraft {
  return {
    title: draft.title,
    start_at: isoToLocalInput(draft.start_at),
    end_at: isoToLocalInput(draft.end_at),
    location: draft.location ?? "",
    description: draft.description ?? "",
    all_day: draft.all_day,
    time_period: draft.time_period,
    repeat_rule: draft.repeat_rule,
    repeat_days: draft.repeat_days ?? [],
  };
}

export function GenerateModal({
  open,
  onClose,
  date,
  defaultPeriod,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  date: string;
  defaultPeriod: TimePeriod;
  onSaved: (count: number) => void;
}) {
  const [phase, setPhase] = useState<Phase>("prompt");
  const [prompt, setPrompt] = useState("");
  const [period, setPeriod] = useState<TimePeriod>(defaultPeriod);
  const [drafts, setDrafts] = useState<EditableDraft[]>([]);
  const [notice, setNotice] = useState<{ status: RoutineGenerateStatus | "save_error"; message: string } | null>(null);

  // Reset to a clean prompt step every time the modal is (re)opened.
  useEffect(() => {
    if (open) {
      setPhase("prompt");
      setPrompt("");
      setPeriod(defaultPeriod);
      setDrafts([]);
      setNotice(null);
    }
  }, [open, defaultPeriod]);

  const generate = async () => {
    setPhase("loading");
    setNotice(null);
    try {
      const result = await routinesApi.generate({ prompt: prompt.trim(), date, period, use_context: true });
      if (result.status === "ok" && result.drafts.length) {
        setDrafts(result.drafts.map(toEditable));
        setPhase("review");
      } else {
        setNotice({
          status: result.status,
          message: result.message || "The AI could not generate routines right now.",
        });
        setPhase("prompt");
      }
    } catch (err) {
      setNotice({
        status: "error",
        message: err instanceof ApiException ? err.message : "Generation failed. Please try again.",
      });
      setPhase("prompt");
    }
  };

  const updateDraft = (index: number, patch: Partial<EditableDraft>) => {
    setDrafts((current) => current.map((draft, i) => (i === index ? { ...draft, ...patch } : draft)));
  };

  const removeDraft = (index: number) => {
    setDrafts((current) => current.filter((_, i) => i !== index));
  };

  const saveAll = async () => {
    const valid = drafts.filter((draft) => draft.title.trim() && draft.start_at);
    if (!valid.length) {
      setNotice({ status: "save_error", message: "Add at least one routine with a title and time." });
      return;
    }
    setPhase("saving");
    setNotice(null);
    try {
      const items = valid.map((draft) => ({
        title: draft.title.trim(),
        description: draft.description.trim() || undefined,
        location: draft.location.trim() || undefined,
        start_at: new Date(draft.start_at).toISOString(),
        end_at: draft.end_at ? new Date(draft.end_at).toISOString() : undefined,
        all_day: draft.all_day,
        time_period: draft.time_period,
        repeat_rule: draft.repeat_rule,
        repeat_days: draft.repeat_days,
      }));
      await routinesApi.createBatch(items);
      onSaved(items.length);
      onClose();
    } catch (err) {
      setNotice({
        status: "save_error",
        message: err instanceof ApiException ? err.message : "Could not save the routines. Nothing was saved.",
      });
      setPhase("review");
    }
  };

  // Count only drafts that would actually save, so the button's label and
  // enabled state match what saveAll() will persist (not the raw card count).
  const savableCount = drafts.filter((draft) => draft.title.trim() && draft.start_at).length;

  const footer =
    phase === "review" || phase === "saving" ? (
      <>
        <Button variant="ghost" onClick={() => setPhase("prompt")} disabled={phase === "saving"}>
          Back
        </Button>
        <Button onClick={saveAll} loading={phase === "saving"} disabled={!savableCount}>
          Save all ({savableCount})
        </Button>
      </>
    ) : (
      <>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={generate} loading={phase === "loading"} disabled={phase === "loading"}>
          <Sparkles size={16} /> Generate
        </Button>
      </>
    );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Generate with AI"
      description="Describe your day. AI drafts routines for you to review and edit — nothing is saved until you approve."
      size="lg"
      footer={footer}
    >
      {phase === "prompt" || phase === "loading" ? (
        <div className="space-y-4">
          {notice ? <Notice notice={notice} /> : null}

          <div>
            <p className="label-mono mb-2">Time of day</p>
            <div className="grid grid-cols-3 gap-2">
              {PERIODS.map((item) => {
                const Icon = item.Icon;
                const active = period === item.key;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setPeriod(item.key)}
                    className={cn(
                      "flex h-10 items-center justify-center gap-1.5 rounded-md border text-sm font-medium transition-colors focus-ring",
                      active
                        ? "grad-primary border-transparent font-semibold text-primary-fg shadow-btn-primary"
                        : "border-border bg-surface-input/45 text-content-muted hover:border-border-strong hover:text-content",
                    )}
                  >
                    <Icon size={15} /> {item.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label htmlFor="ai-routine-prompt" className="label-mono mb-2 block">
              What should this routine cover?
            </label>
            <textarea
              id="ai-routine-prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="e.g. A focused study block, a workout, and a short break before dinner."
              rows={4}
              disabled={phase === "loading"}
              className="w-full resize-y rounded-md border border-border bg-surface-input px-3 py-2 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30 disabled:opacity-60"
            />
            <p className="mt-1.5 text-[12px] text-content-subtle">
              AI uses your open tasks and existing routines on this date as context.
            </p>
          </div>

          {phase === "loading" ? (
            <div className="flex items-center gap-2 rounded-md border border-primary/20 bg-primary/[0.06] px-3 py-2.5 text-sm text-content-muted">
              <Wand2 size={16} className="animate-pulse-soft text-primary-bright" />
              Drafting your routines…
            </div>
          ) : null}
        </div>
      ) : (
        <div className="space-y-3">
          {notice ? <Notice notice={notice} /> : null}
          <p className="text-[13px] text-content-muted">
            Review and edit the drafts below, then save. Remove anything you don&apos;t want.
          </p>
          {drafts.length ? (
            drafts.map((draft, index) => (
              <DraftCard
                key={index}
                draft={draft}
                disabled={phase === "saving"}
                onChange={(patch) => updateDraft(index, patch)}
                onRemove={() => removeDraft(index)}
              />
            ))
          ) : (
            <div className="rounded-md border border-dashed border-border bg-surface-input/25 px-4 py-6 text-center text-[13px] text-content-muted">
              No drafts left. Go back to generate again.
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function Notice({ notice }: { notice: { status: RoutineGenerateStatus | "save_error"; message: string } }) {
  const isConfig = notice.status === "not_configured";
  const tone = notice.status === "blocked" || notice.status === "not_configured"
    ? "border-warning/35 bg-warning/10 text-warning"
    : "border-danger/35 bg-danger/10 text-danger";
  return (
    <div className={cn("flex items-start gap-2 rounded-md border px-3 py-2.5 text-[13px]", tone)}>
      <AlertTriangle size={15} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        <p>{notice.message}</p>
        {isConfig ? (
          <Link
            href="/dashboard/settings"
            className="mt-1 inline-flex items-center gap-1 text-[12px] font-medium underline underline-offset-2 hover:opacity-80"
          >
            <Settings2 size={12} /> Open AI Providers settings
          </Link>
        ) : null}
      </div>
    </div>
  );
}

function DraftCard({
  draft,
  disabled,
  onChange,
  onRemove,
}: {
  draft: EditableDraft;
  disabled: boolean;
  onChange: (patch: Partial<EditableDraft>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="glass-tile animate-fade-in space-y-2 p-3">
      <div className="flex items-center gap-2">
        <input
          value={draft.title}
          onChange={(event) => onChange({ title: event.target.value })}
          placeholder="Routine title"
          disabled={disabled}
          className="h-9 w-full rounded-md border border-border bg-surface-input px-3 text-sm font-medium text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30 disabled:opacity-60"
        />
        <button
          onClick={onRemove}
          aria-label="Remove draft"
          disabled={disabled}
          className="shrink-0 rounded-lg p-2 text-content-subtle transition-colors hover:bg-danger/10 hover:text-danger focus-ring disabled:pointer-events-none disabled:opacity-50"
        >
          <Trash2 size={15} />
        </button>
      </div>
      <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
        <input
          type="datetime-local"
          value={draft.start_at}
          onChange={(event) => onChange({ start_at: event.target.value })}
          aria-label="Start time"
          disabled={disabled}
          className="h-9 rounded-md border border-border bg-surface-input px-3 text-sm text-content focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30 disabled:opacity-60"
        />
        <select
          value={draft.repeat_rule}
          onChange={(event) => onChange({ repeat_rule: event.target.value as RepeatRule })}
          aria-label="Repeat"
          disabled={disabled}
          className="h-9 rounded-md border border-border bg-surface-input px-3 text-sm text-content focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30 disabled:opacity-60"
        >
          {REPEAT_OPTIONS.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <input
        value={draft.location}
        onChange={(event) => onChange({ location: event.target.value })}
        placeholder="Location (optional)"
        disabled={disabled}
        className="h-9 w-full rounded-md border border-border bg-surface-input px-3 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30 disabled:opacity-60"
      />
      {draft.description ? (
        <p className="line-clamp-2 text-[12px] text-content-subtle">{draft.description}</p>
      ) : null}
    </div>
  );
}
