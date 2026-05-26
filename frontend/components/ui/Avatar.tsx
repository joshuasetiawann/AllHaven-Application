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
        "inline-flex items-center justify-center rounded-full border border-primary/30 bg-primary/10 font-semibold text-primary",
        size === "sm" ? "h-7 w-7 text-[12px]" : "h-9 w-9 text-[13px]",
        className,
      )}
    >
      {initials}
    </span>
  );
}
