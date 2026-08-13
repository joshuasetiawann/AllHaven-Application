import { cn } from "@/lib/format";

export function Avatar({
  initials,
  size = "md",
  className,
}: {
  initials: string;
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "grad-primary inline-flex items-center justify-center rounded-full font-semibold text-primary-fg shadow-[0_0_18px_rgb(var(--color-primary)/0.35)]",
        size === "sm" ? "h-7 w-7 text-[12px]" : "h-9 w-9 text-[13px]",
        className,
      )}
    >
      {initials}
    </span>
  );
}
