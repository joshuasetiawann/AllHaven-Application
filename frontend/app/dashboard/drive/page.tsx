"use client";

import { useEffect, useState } from "react";
import { FileText, FolderOpen, HardDrive, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { EmptyState, Loading } from "@/components/ui/States";
import { IntegrationStatusBanner } from "@/components/modules/IntegrationStatusBanner";
import { settingsApi } from "@/lib/api";
import type { Integration } from "@/types";

export default function DrivePage() {
  const [integration, setIntegration] = useState<Integration | undefined>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    settingsApi
      .integrations()
      .then((r) => setIntegration(r.integrations.find((i) => i.key === "drive_storage")))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell>
      <PageHeader title="Drive" subtitle="Workspace file storage — local or Supabase." />
      {loading ? (
        <Loading />
      ) : (
        <>
          <IntegrationStatusBanner integration={integration} label="Drive Storage" />

          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              {/* Honest: upload UI preview, wiring not enabled */}
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border px-6 py-14 text-center">
                <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-surface-input text-content-subtle">
                  <UploadCloud size={22} />
                </span>
                <p className="text-sm font-medium text-content">Upload files</p>
                <p className="mt-1 max-w-sm text-[13px] text-content-muted">
                  File upload wiring is not enabled yet in this MVP. The storage adapter and status are
                  ready — connect a provider in Settings to prepare it.
                </p>
                <button
                  disabled
                  className="mt-4 inline-flex cursor-not-allowed items-center gap-2 rounded-md border border-border px-4 py-2 text-[13px] text-content-subtle opacity-60"
                >
                  <UploadCloud size={15} /> Choose files (disabled)
                </button>
              </div>
            </Card>

            <Card>
              <div className="mb-3 flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
                  <HardDrive size={18} />
                </span>
                <p className="text-sm font-semibold text-content">Storage</p>
              </div>
              <dl className="space-y-2.5 text-[13px]">
                <div className="flex items-center justify-between">
                  <dt className="text-content-muted">Provider</dt>
                  <dd className="text-content">{integration?.public_config?.provider || "local"}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-content-muted">Status</dt>
                  <dd className="text-content">{integration?.detail ?? "Not configured"}</dd>
                </div>
              </dl>
            </Card>
          </div>

          <div className="mt-5">
            <EmptyState
              title="No files yet"
              description="When upload is enabled, your workspace files will appear here."
              icon={<FolderOpen size={20} />}
            />
          </div>
        </>
      )}
    </AppShell>
  );
}
