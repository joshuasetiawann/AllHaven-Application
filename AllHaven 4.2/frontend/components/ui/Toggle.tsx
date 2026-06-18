import { cn } from "@/lib/format";

export function Toggle({
  checked,
  onChange,
  disabled = false,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border p-[2px] transition-all focus-ring",
        checked
          ? "border-transparent bg-[linear-gradient(90deg,rgb(var(--color-primary)),rgb(var(--color-secondary)))] shadow-toggle-on"
          : "border-border bg-content/10",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <span
        className={cn(
          "inline-block h-5 w-5 transform rounded-full shadow transition-transform",
          checked ? "translate-x-[18px] bg-white" : "translate-x-0 bg-[#8A93A6]",
        )}
      />
    </button>
  );
}
