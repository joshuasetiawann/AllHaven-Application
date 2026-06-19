import { Bot, Menu, Search } from "lucide-react";
import { Skeleton } from "@/components/ui/States";

type LoadingScope = "app" | "dashboard";

function RailSkeleton() {
  return (
    <aside className="hidden h-screen w-[80px] shrink-0 border-r border-border bg-bg-deep/92 p-4 md:flex xl:w-[280px] xl:p-5">
      <div className="flex w-full flex-col gap-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-xl" />
          <div className="hidden min-w-0 flex-1 space-y-2 xl:block">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-3 w-14" />
          </div>
        </div>
        <Skeleton className="h-11 rounded-xl" />
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="flex items-center gap-3">
              <Skeleton className="h-9 w-9 rounded-lg" />
              <Skeleton className="hidden h-4 flex-1 xl:block" />
            </div>
          ))}
        </div>
        <div className="mt-auto space-y-3">
          <Skeleton className="h-9 rounded-lg" />
          <Skeleton className="h-9 rounded-lg" />
        </div>
      </div>
    </aside>
  );
}

function TopbarSkeleton() {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg/85 px-3 py-3 backdrop-blur-xl sm:px-5 lg:px-8">
      <div className="mx-auto flex max-w-[1480px] items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface-input text-content-muted md:hidden">
          <Menu size={18} />
        </span>
        <div className="flex h-10 min-w-0 flex-1 items-center gap-2 rounded-xl border border-border bg-surface-input px-3 sm:max-w-lg">
          <Search size={16} className="text-content-subtle" />
          <Skeleton className="h-4 flex-1" />
        </div>
        <Skeleton className="hidden h-10 w-48 rounded-full lg:block" />
        <Skeleton className="h-10 w-10 rounded-xl" />
        <Skeleton className="h-10 w-10 rounded-full" />
      </div>
    </header>
  );
}

function PageContentSkeleton({ scope }: { scope: LoadingScope }) {
  const panelRows = scope === "dashboard" ? 4 : 3;

  return (
    <main className="mx-auto w-full max-w-[1480px] animate-page-in px-3 py-4 sm:px-5 sm:py-5 lg:px-8 lg:py-7">
      <div className="mb-7 flex flex-col gap-4 border-b border-border/70 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex gap-2">
            <Skeleton className="h-6 w-20 rounded-full" />
            <Skeleton className="h-6 w-24 rounded-full" />
          </div>
          <Skeleton className="h-9 w-[min(420px,80vw)]" />
          <Skeleton className="h-4 w-[min(620px,88vw)]" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-10 w-28 rounded-lg" />
          <Skeleton className="h-10 w-32 rounded-lg" />
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <section className="space-y-5 xl:col-span-2">
          <div className="panel-gradient p-5">
            <div className="mb-5 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
                <Bot size={18} />
              </span>
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-44" />
                <Skeleton className="h-3 w-64 max-w-full" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="rounded-xl border border-border bg-surface-input/65 p-4">
                  <Skeleton className="mb-3 h-7 w-7 rounded-lg" />
                  <Skeleton className="mb-3 h-3 w-20" />
                  <Skeleton className="h-7 w-24" />
                </div>
              ))}
            </div>
          </div>

          <div className="panel p-5">
            <Skeleton className="mb-4 h-5 w-40" />
            <Skeleton className="mb-4 h-10 w-56" />
            <div className="flex h-48 items-end gap-3 border-b border-border pb-3">
              {[42, 68, 54, 80, 60].map((height, index) => (
                <Skeleton
                  key={index}
                  className="flex-1 rounded-t-lg"
                  style={{ height: `${height}%` }}
                />
              ))}
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-4 w-52" />
            </div>
          </div>
        </section>

        <aside className="space-y-5">
          {Array.from({ length: panelRows }).map((_, panelIndex) => (
            <div key={panelIndex} className="panel p-5">
              <div className="mb-4 flex items-center gap-3">
                <Skeleton className="h-9 w-9 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, rowIndex) => (
                  <Skeleton key={rowIndex} className="h-10 rounded-lg" />
                ))}
              </div>
            </div>
          ))}
        </aside>
      </div>
    </main>
  );
}

export function AppLoadingSkeleton({ scope = "app" }: { scope?: LoadingScope }) {
  return (
    <div className="min-h-screen overflow-x-hidden bg-bg text-content">
      <div className="flex min-h-screen">
        <RailSkeleton />
        <div className="min-w-0 flex-1">
          <TopbarSkeleton />
          <PageContentSkeleton scope={scope} />
        </div>
      </div>
    </div>
  );
}
