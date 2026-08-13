import { Skeleton } from "@/components/ui/States";

/** Full-page content loader for the Routine view (mirrors the real layout). */
export function RoutineSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading routines">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="panel flex items-center gap-3 p-4">
            <Skeleton className="h-10 w-10 rounded-[11px]" />
            <div className="space-y-2">
              <Skeleton className="h-3 w-14" />
              <Skeleton className="h-5 w-10" />
            </div>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="panel flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-2">
          <Skeleton className="h-8 w-20 rounded-[9px]" />
          <Skeleton className="h-8 w-20 rounded-[9px]" />
          <Skeleton className="h-8 w-16 rounded-[9px]" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-44 rounded-md" />
          <Skeleton className="h-9 w-36 rounded-md" />
        </div>
      </div>

      {/* Date strip */}
      <div className="flex gap-2 overflow-hidden">
        {Array.from({ length: 7 }).map((_, i) => (
          <Skeleton key={i} className="h-[4.75rem] w-[4.5rem] shrink-0 rounded-xl" />
        ))}
      </div>

      {/* Timeline card + right column (dial + habits) */}
      <div className="grid items-start gap-5 lg:grid-cols-[2fr_1fr]">
        <div className="panel space-y-5 p-6">
          <div className="flex items-center gap-2.5">
            <Skeleton className="h-8 w-8 rounded-md" />
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-44" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex gap-4">
              <Skeleton className="mt-3 h-3 w-14 shrink-0" />
              <Skeleton className="h-20 flex-1 rounded-[13px]" />
            </div>
          ))}
        </div>

        <div className="space-y-5">
          <div className="panel flex flex-col items-center gap-4 p-[22px]">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-32 w-32 rounded-full" />
          </div>
          <div className="panel space-y-4 p-[22px]">
            <Skeleton className="h-4 w-16" />
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <Skeleton className="h-7 w-7 rounded-sm" />
                  <Skeleton className="h-4 w-28" />
                </div>
                <Skeleton className="h-3 w-16" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
