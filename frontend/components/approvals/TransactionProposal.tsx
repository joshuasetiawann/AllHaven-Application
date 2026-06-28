"use client";

import type { ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { formatCurrency, formatDate } from "@/lib/format";

// The three finance-create tools share one backend handler and one payload shape.
export const FINANCE_CREATE_TOOLS = new Set([
  "create_transaction",
  "create_transaction_draft",
  "create_transaction_after_approval",
]);

export function isTransactionTool(name: string): boolean {
  return FINANCE_CREATE_TOOLS.has(name);
}

/** Local YYYY-MM-DD — mirrors the backend's "empty date defaults to today". */
export function todayIso(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function asString(value: unknown): string {
  if (typeof value === "string") return value;
  return value == null ? "" : String(value);
}

export interface TxnView {
  type: string;
  amount: number | null;
  currency: string;
  categoryId: string | null;
  description: string;
  date: string; // raw payload value (may be empty)
  effectiveDate: string; // date, or today when empty (matches backend)
}

export function readTransaction(payload: Record<string, unknown>): TxnView {
  const raw = payload.amount;
  const amount =
    typeof raw === "number" && Number.isFinite(raw)
      ? raw
      : typeof raw === "string" && raw.trim() !== "" && !Number.isNaN(Number(raw))
        ? Number(raw)
        : null;
  const date = asString(payload.transaction_date);
  return {
    type: asString(payload.type).toUpperCase(),
    amount,
    currency: (asString(payload.currency) || "IDR").toUpperCase(),
    categoryId: asString(payload.category_id).trim() || null,
    description: asString(payload.description),
    date,
    effectiveDate: date.trim() || todayIso(),
  };
}

/**
 * Required-field problems that must block execution. Category is optional
 * (renders as "Uncategorized") and an empty date defaults to today, so neither
 * is an error here.
 */
export function transactionPayloadErrors(payload: Record<string, unknown>): string[] {
  const view = readTransaction(payload);
  const errors: string[] = [];
  if (view.type !== "INCOME" && view.type !== "EXPENSE") {
    errors.push("Type must be Income or Expense.");
  }
  if (view.amount === null || view.amount <= 0) {
    errors.push("Amount must be a number greater than 0.");
  }
  return errors;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <dt className="shrink-0 text-[11px] font-medium uppercase tracking-wide text-content-subtle">{label}</dt>
      <dd className="min-w-0 break-words text-right text-[13px] text-content">{children}</dd>
    </div>
  );
}

/** Readable, non-JSON view of a finance-transaction proposal. */
export function TransactionSummary({ payload }: { payload: Record<string, unknown> }) {
  const v = readTransaction(payload);
  const isExpense = v.type === "EXPENSE";
  return (
    <dl className="mt-2 divide-y divide-border/60 rounded-lg border border-border bg-bg/40 px-3 py-1.5">
      <Row label="Type">
        <Badge tone={isExpense ? "danger" : "success"}>{v.type || "—"}</Badge>
      </Row>
      <Row label="Amount">
        <span className={isExpense ? "text-danger" : "text-success"}>
          {v.amount !== null ? formatCurrency(v.amount, v.currency) : "—"}
        </span>
      </Row>
      <Row label="Category">
        {v.categoryId ? (
          <span className="font-mono text-[11.5px] text-content-muted">{v.categoryId}</span>
        ) : (
          <span className="text-content-subtle">Uncategorized</span>
        )}
      </Row>
      <Row label="Date">
        {v.date.trim() ? formatDate(v.effectiveDate) : `Today (${formatDate(v.effectiveDate)})`}
      </Row>
      <Row label="Description">{v.description || <span className="text-content-subtle">—</span>}</Row>
    </dl>
  );
}

/** Structured editor — replaces raw-JSON editing for transaction proposals. */
export function TransactionEditForm({
  value,
  onChange,
  disabled,
}: {
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
  disabled?: boolean;
}) {
  const v = readTransaction(value);
  const set = (patch: Record<string, unknown>) => onChange({ ...value, ...patch });
  const errors = transactionPayloadErrors(value);
  return (
    <div className="space-y-3">
      <Select
        label="Type"
        value={v.type === "INCOME" ? "INCOME" : "EXPENSE"}
        disabled={disabled}
        onChange={(e) => set({ type: e.target.value })}
      >
        <option value="EXPENSE">Expense</option>
        <option value="INCOME">Income</option>
      </Select>
      <div className="grid grid-cols-[1fr_120px] gap-3">
        <Input
          label="Amount"
          type="number"
          min="0"
          step="any"
          inputMode="decimal"
          disabled={disabled}
          value={v.amount === null ? "" : String(v.amount)}
          onChange={(e) => set({ amount: e.target.value === "" ? "" : Number(e.target.value) })}
        />
        <Input
          label="Currency"
          disabled={disabled}
          value={v.currency}
          onChange={(e) => set({ currency: e.target.value.toUpperCase().slice(0, 3) })}
        />
      </div>
      <Input
        label="Category ID"
        hint="Leave empty for Uncategorized"
        disabled={disabled}
        value={asString(value.category_id)}
        onChange={(e) => set({ category_id: e.target.value })}
      />
      <Input
        label="Date"
        type="date"
        disabled={disabled}
        value={v.date.trim() || todayIso()}
        onChange={(e) => set({ transaction_date: e.target.value })}
      />
      <Input
        label="Description"
        disabled={disabled}
        value={v.description}
        onChange={(e) => set({ description: e.target.value })}
      />
      {errors.length > 0 ? (
        <ul className="space-y-1 text-[12px] text-danger">
          {errors.map((msg) => (
            <li key={msg}>• {msg}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
