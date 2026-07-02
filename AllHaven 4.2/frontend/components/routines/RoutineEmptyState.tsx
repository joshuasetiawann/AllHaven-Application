import { CalendarRange, Plus, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/Button";

/** Page-level empty state with two clear CTAs: Add routine and Generate with AI. */
export function RoutineEmptyState({
  onAdd,
  onGenerate,
}: {
  onAdd: () => void;
  onGenerate: () => void;
}) {
  return (
    <div className="panel-gradient flex animate-fade-in flex-col items-center justify-center px-6 py-14 text-center">
      <span className="grad-primary mb-4 flex h-14 w-14 items-center justify-center rounded-xl text-primary-fg shadow-btn-primary">
        <CalendarRange size={24} />
      </span>
      <h3 className="text-base font-semibold text-content">Plan your day with calm</h3>
      <p className="mt-1 max-w-md text-[13px] leading-relaxed text-content-muted">
        Nothing scheduled here yet. Add a block yourself, or let AI draft a balanced
        plan for this day — you review and approve every item before it&apos;s saved.
      </p>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        <Button onClick={onAdd}>
          <Plus size={16} /> Add block
        </Button>
        <Button variant="secondary" onClick={onGenerate}>
          <Sparkles size={16} /> Generate with AI
        </Button>
      </div>
    </div>
  );
}
