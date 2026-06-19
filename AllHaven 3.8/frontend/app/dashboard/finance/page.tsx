"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Plus,
  SlidersHorizontal,
  Trash2,
  Wallet,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Modal } from "@/components/ui/Modal";
import { BarChart } from "@/components/ui/BarChart";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { financeApi, ApiException } from "@/lib/api";
import { cn, formatCurrency, formatDate, monthLabel } from "@/lib/format";
import type { FinanceCategory, FinanceReport, FinanceType, Transaction } from "@/types";

type ReportMode = "month" | "week";

const toIsoDate = (date: Date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

const parseLocalDate = (value: string) => {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
};

const todayIso = () => toIsoDate(new Date());

const startOfWeek = (date: Date) => {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const mondayOffset = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - mondayOffset);
  return d;
};

const addDays = (date: Date, days: number) => {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  d.setDate(d.getDate() + days);
  return d;
};

const addMonths = (date: Date, months: number) =>
  new Date(date.getFullYear(), date.getMonth() + months, 1);

function periodFor(mode: ReportMode, anchor: Date) {
  if (mode === "week") {
    const start = startOfWeek(anchor);
    const end = addDays(start, 6);
    return {
      start: toIsoDate(start),
      end: toIsoDate(end),
      label: `${formatDate(toIsoDate(start))} - ${formatDate(toIsoDate(end))}`,
    };
  }
  const start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
  return {
    start: toIsoDate(start),
    end: toIsoDate(end),
    label: monthLabel(anchor.getFullYear(), anchor.getMonth() + 1),
  };
}

const isInRange = (dateValue: string, start: string, end: string) =>
  dateValue >= start && dateValue <= end;

export default function FinancePage() {
  const toast = useToast();
  const [mode, setMode] = useState<ReportMode>("month");
  const [anchorDate, setAnchorDate] = useState(() => new Date());
  const period = useMemo(() => periodFor(mode, anchorDate), [mode, anchorDate]);

  const [categories, setCategories] = useState<FinanceCategory[]>([]);
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [recentTransactions, setRecentTransactions] = useState<Transaction[]>([]);
  const [report, setReport] = useState<FinanceReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [txnOpen, setTxnOpen] = useState(false);
  const [catOpen, setCatOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const [txnForm, setTxnForm] = useState({
    type: "EXPENSE" as FinanceType,
    amount: "",
    category_id: "",
    description: "",
    transaction_date: todayIso(),
  });
  const [catForm, setCatForm] = useState({ name: "", type: "EXPENSE" as FinanceType });

  const load = async () => {
    setError(null);
    try {
      const [cats, txns, recent, rep] = await Promise.all([
        financeApi.listCategories(),
        financeApi.listTransactions({ start: period.start, end: period.end, currency: "IDR", limit: 500 }),
        financeApi.listTransactions({ limit: 8 }),
        financeApi.report({ start: period.start, end: period.end, periodType: mode, currency: "IDR" }),
      ]);
      setCategories(cats);
      setTransactions(txns);
      setRecentTransactions(recent);
      setReport(rep);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load finance data.");
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, period.start, period.end]);

  const trendBars = useMemo(() => {
    if (mode === "week") {
      const labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
      const buckets = labels.map(() => 0);
      (transactions ?? []).forEach((t) => {
        if (t.type !== "EXPENSE") return;
        const day = (parseLocalDate(t.transaction_date).getDay() + 6) % 7;
        buckets[day] += t.amount;
      });
      return labels.map((label, i) => ({ label, value: buckets[i] }));
    }
    const buckets = [0, 0, 0, 0, 0];
    (transactions ?? []).forEach((t) => {
      if (t.type !== "EXPENSE") return;
      const d = parseLocalDate(t.transaction_date);
      buckets[Math.min(4, Math.floor((d.getDate() - 1) / 7))] += t.amount;
    });
    return buckets.map((value, i) => ({ label: `W${i + 1}`, value }));
  }, [transactions, mode]);

  const latestOutsidePeriod = useMemo(
    () => recentTransactions.filter((t) => !isInRange(t.transaction_date, period.start, period.end)).slice(0, 5),
    [recentTransactions, period.start, period.end],
  );

  const periodInputValue = useMemo(() => {
    if (mode === "week") return period.start;
    const d = parseLocalDate(period.start);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  }, [mode, period.start]);

  const openTransactionModal = () => {
    const today = todayIso();
    const defaultDate = isInRange(today, period.start, period.end) ? today : period.start;
    setTxnForm((cur) => ({ ...cur, transaction_date: defaultDate }));
    setTxnOpen(true);
  };

  const shiftPeriod = (amount: number) => {
    setAnchorDate((cur) => (mode === "week" ? addDays(cur, amount * 7) : addMonths(cur, amount)));
  };

  const changePeriodInput = (value: string) => {
    if (!value) return;
    if (mode === "month") {
      const [y, m] = value.split("-").map(Number);
      if (y && m) setAnchorDate(new Date(y, m - 1, 1));
      return;
    }
    setAnchorDate(parseLocalDate(value));
  };

  const createTransaction = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const created = await financeApi.createTransaction({
        type: txnForm.type,
        amount: Number(txnForm.amount),
        category_id: txnForm.category_id || null,
        description: txnForm.description || null,
        transaction_date: txnForm.transaction_date,
      });
      setTxnOpen(false);
      setTxnForm({ type: "EXPENSE", amount: "", category_id: "", description: "", transaction_date: todayIso() });
      if (isInRange(created.transaction_date, period.start, period.end)) {
        await load();
      } else {
        setAnchorDate(parseLocalDate(created.transaction_date));
      }
      toast.success("Transaction saved", `${txnForm.type === "INCOME" ? "Income" : "Expense"} ${formatCurrency(created.amount, created.currency)} recorded.`);
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Failed to create transaction.";
      setError(message);
      toast.danger("Could not save transaction", message);
    } finally {
      setSaving(false);
    }
  };

  const createCategory = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await financeApi.createCategory({ name: catForm.name, type: catForm.type });
      toast.success("Category added", catForm.name);
      setCatForm({ name: "", type: "EXPENSE" });
      await load();
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Failed to create category.";
      setError(message);
      toast.danger("Category failed", message);
    } finally {
      setSaving(false);
    }
  };

  const removeTransaction = async (txn: Transaction) => {
    setTransactions((prev) => prev?.filter((t) => t.id !== txn.id) ?? prev);
    setRecentTransactions((prev) => prev.filter((t) => t.id !== txn.id));
    try {
      await financeApi.removeTransaction(txn.id);
      await load();
      toast.success("Transaction deleted");
    } catch {
      toast.danger("Delete failed", "The transaction could not be removed.");
      void load();
    }
  };

  const moveTransactionToReport = async (txn: Transaction) => {
    const today = todayIso();
    const transactionDate = isInRange(today, period.start, period.end) ? today : period.start;
    setSaving(true);
    setError(null);
    try {
      await financeApi.updateTransaction(txn.id, { transaction_date: transactionDate });
      await load();
      toast.success("Transaction moved", `Now counted in ${period.label}.`);
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Failed to move transaction into this report.";
      setError(message);
      toast.danger("Move failed", message);
    } finally {
      setSaving(false);
    }
  };

  const removeCategory = async (category: FinanceCategory) => {
    setCategories((prev) => prev.filter((c) => c.id !== category.id));
    try {
      await financeApi.removeCategory(category.id);
      toast.success("Category deleted", category.name);
    } catch {
      toast.danger("Delete failed", "The category could not be removed.");
      void load();
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Finance"
        subtitle={`Cashflow report - ${period.label}`}
        actions={
          <>
            <Button variant="ghost" onClick={() => setCatOpen(true)}>
              <SlidersHorizontal size={15} /> Categories
            </Button>
            <Button onClick={openTransactionModal}>
              <Plus size={16} /> New transaction
            </Button>
          </>
        }
      />

      <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="inline-flex rounded-lg border border-border bg-surface-input p-0.5 text-[12.5px]">
          {(["month", "week"] as ReportMode[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setMode(item)}
              className={cn(
                "rounded-md px-3 py-1.5 capitalize transition-colors",
                mode === item ? "bg-surface-high text-primary" : "text-content-muted hover:text-content",
              )}
            >
              {item === "month" ? "Monthly" : "Weekly"}
            </button>
          ))}
        </div>
        <div className="inline-flex w-full items-center rounded-lg border border-border bg-surface-input p-0.5 sm:w-auto">
          <button
            type="button"
            onClick={() => shiftPeriod(-1)}
            className="flex h-8 w-8 items-center justify-center rounded-md text-content-muted transition-colors hover:bg-surface-high hover:text-content"
            aria-label="Previous period"
          >
            <ChevronLeft size={15} />
          </button>
          <label className="flex h-8 min-w-0 flex-1 items-center gap-2 border-x border-border px-2 text-[12px] text-content-muted sm:flex-none">
            <CalendarDays size={13} />
            <input
              type={mode === "month" ? "month" : "date"}
              value={periodInputValue}
              onChange={(e) => changePeriodInput(e.target.value)}
              className="min-w-0 flex-1 bg-transparent text-[12.5px] text-content outline-none sm:w-[132px] sm:flex-none"
            />
          </label>
          <button
            type="button"
            onClick={() => shiftPeriod(1)}
            className="flex h-8 w-8 items-center justify-center rounded-md text-content-muted transition-colors hover:bg-surface-high hover:text-content"
            aria-label="Next period"
          >
            <ChevronRight size={15} />
          </button>
        </div>
        <Button size="sm" variant="ghost" onClick={() => setAnchorDate(new Date())} className="w-full sm:w-auto">
          Current
        </Button>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !transactions || !report ? (
        <Loading />
      ) : (
        <div className="animate-fade-in space-y-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4">
            <Card padding="md" hover>
              <div className="flex items-center justify-between gap-2">
                <p className="label-mono">Income</p>
                <span className="flex h-7 w-7 items-center justify-center rounded-md border border-success/30 bg-success/10 text-success">
                  <ArrowDownLeft size={14} />
                </span>
              </div>
              <p className="mt-2 text-xl font-semibold tabular-nums text-success sm:text-2xl">
                {formatCurrency(report.total_income, report.currency)}
              </p>
            </Card>
            <Card padding="md" hover>
              <div className="flex items-center justify-between gap-2">
                <p className="label-mono">Expense</p>
                <span className="flex h-7 w-7 items-center justify-center rounded-md border border-danger/30 bg-danger/10 text-danger">
                  <ArrowUpRight size={14} />
                </span>
              </div>
              <p className="mt-2 text-xl font-semibold tabular-nums text-danger sm:text-2xl">
                {formatCurrency(report.total_expense, report.currency)}
              </p>
            </Card>
            <Card gradient padding="md" hover className="col-span-2 border-primary/30 sm:col-span-1">
              <div className="flex items-center justify-between gap-2">
                <p className="label-mono">Balance</p>
                <span className="flex h-7 w-7 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary">
                  <Wallet size={14} />
                </span>
              </div>
              <p className={cn(
                "mt-2 text-xl font-semibold tabular-nums sm:text-2xl",
                report.balance < 0 ? "text-danger" : "text-content",
              )}>
                {formatCurrency(report.balance, report.currency)}
              </p>
            </Card>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                title="Transactions"
                subtitle={`${report.transaction_count} in this ${mode}`}
                icon={<Wallet size={18} />}
              />
              {transactions.length === 0 ? (
                <div className="space-y-4">
                  <EmptyState
                    title="No transactions in this report"
                    description="Change the period, or record a transaction for the selected report."
                  />
                  {latestOutsidePeriod.length ? (
                    <div className="rounded-lg border border-border bg-surface-input/45 p-3">
                      <div className="mb-2">
                        <p className="text-[12px] font-medium text-content-muted">
                          Archived records outside {period.label}
                        </p>
                        <p className="mt-0.5 text-[11.5px] text-content-subtle">
                          These records are not counted because their dates are outside this report.
                        </p>
                      </div>
                      <ul className="space-y-1.5">
                        {latestOutsidePeriod.map((txn) => (
                          <li key={txn.id} className="flex flex-col gap-2 rounded-md px-2 py-1.5 sm:flex-row sm:items-center sm:justify-between">
                            <span className="min-w-0">
                              <span className="block truncate text-[13px] text-content">
                                {txn.description || txn.category_name_snapshot || (txn.type === "INCOME" ? "Income" : "Expense")}
                              </span>
                              <span className="label-mono">
                                {formatDate(txn.transaction_date)} - {txn.type === "INCOME" ? "+" : "-"}
                                {formatCurrency(txn.amount, txn.currency)}
                              </span>
                            </span>
                            <span className="flex shrink-0 flex-wrap items-center gap-1.5">
                              <button
                                type="button"
                                onClick={() => void moveTransactionToReport(txn)}
                                disabled={saving}
                                className="rounded-md border border-primary/40 px-2 py-1 text-[11.5px] text-primary transition-colors hover:border-primary disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                Move to {mode}
                              </button>
                              <button
                                type="button"
                                onClick={() => setAnchorDate(parseLocalDate(txn.transaction_date))}
                                className="rounded-md border border-border px-2 py-1 text-[11.5px] text-content-muted transition-colors hover:border-primary/50 hover:text-primary"
                              >
                                Open old period
                              </button>
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {transactions.map((txn) => {
                    const income = txn.type === "INCOME";
                    return (
                      <li key={txn.id} className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex min-w-0 items-center gap-3">
                          <span
                            className={
                              "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border " +
                              (income
                                ? "border-success/30 bg-success/10 text-success"
                                : "border-danger/30 bg-danger/10 text-danger")
                            }
                          >
                            {income ? <ArrowDownLeft size={16} /> : <ArrowUpRight size={16} />}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate text-sm text-content">
                              {txn.description || txn.category_name_snapshot || (income ? "Income" : "Expense")}
                            </p>
                            <p className="label-mono">
                              {formatDate(txn.transaction_date)}
                              {txn.category_name_snapshot ? ` - ${txn.category_name_snapshot}` : ""}
                            </p>
                          </div>
                        </div>
                        <div className="flex w-full shrink-0 items-center justify-between gap-3 sm:w-auto sm:justify-end">
                          <span className={"text-sm font-semibold " + (income ? "text-success" : "text-danger")}>
                            {income ? "+" : "-"}
                            {formatCurrency(txn.amount, txn.currency)}
                          </span>
                          <button
                            onClick={() => removeTransaction(txn)}
                            className="text-content-subtle transition-colors hover:text-danger"
                            aria-label="Delete transaction"
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>

            <Card>
              <CardHeader
                title={mode === "month" ? "Weekly spend" : "Daily spend"}
                subtitle={period.label}
                icon={<Wallet size={18} />}
              />
              <BarChart data={trendBars} height={140} />
              <p className="mt-4 border-t border-border pt-3 text-[12px] text-content-subtle">
                AllHaven tracks cashflow. It does not provide financial advice.
              </p>
            </Card>
          </div>
        </div>
      )}

      <Modal
        open={txnOpen}
        onClose={() => setTxnOpen(false)}
        title="New transaction"
        footer={
          <>
            <Button variant="ghost" onClick={() => setTxnOpen(false)}>
              Cancel
            </Button>
            <Button form="txn-form" type="submit" loading={saving} disabled={!txnForm.amount}>
              Record
            </Button>
          </>
        }
      >
        <form id="txn-form" onSubmit={createTransaction} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Select
              label="Type"
              value={txnForm.type}
              onChange={(e) => setTxnForm({ ...txnForm, type: e.target.value as FinanceType })}
            >
              <option value="EXPENSE">Expense</option>
              <option value="INCOME">Income</option>
            </Select>
            <Input
              id="amount"
              label="Amount"
              type="number"
              min="0.01"
              step="0.01"
              required
              placeholder="0"
              value={txnForm.amount}
              onChange={(e) => setTxnForm({ ...txnForm, amount: e.target.value })}
            />
          </div>
          <Select
            label="Category"
            value={txnForm.category_id}
            onChange={(e) => setTxnForm({ ...txnForm, category_id: e.target.value })}
          >
            <option value="">Uncategorized</option>
            {categories
              .filter((c) => c.type === txnForm.type)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </Select>
          <Input
            id="txn-date"
            label="Date"
            type="date"
            required
            value={txnForm.transaction_date}
            onChange={(e) => setTxnForm({ ...txnForm, transaction_date: e.target.value })}
          />
          <Input
            id="txn-desc"
            label="Description"
            placeholder="Optional"
            value={txnForm.description}
            onChange={(e) => setTxnForm({ ...txnForm, description: e.target.value })}
          />
        </form>
      </Modal>

      <Modal open={catOpen} onClose={() => setCatOpen(false)} title="Categories">
        <form onSubmit={createCategory} className="mb-4 grid gap-2 sm:grid-cols-[1fr_auto_auto] sm:items-end">
          <Input
            id="cat-name"
            label="New category"
            placeholder="Salary, Food"
            value={catForm.name}
            onChange={(e) => setCatForm({ ...catForm, name: e.target.value })}
          />
          <Select
            value={catForm.type}
            onChange={(e) => setCatForm({ ...catForm, type: e.target.value as FinanceType })}
            className="w-full sm:w-28"
          >
            <option value="EXPENSE">Expense</option>
            <option value="INCOME">Income</option>
          </Select>
          <Button type="submit" loading={saving} disabled={!catForm.name.trim()} className="w-full sm:w-auto">
            Add
          </Button>
        </form>

        {categories.length === 0 ? (
          <p className="py-4 text-center text-[13px] text-content-muted">No categories yet.</p>
        ) : (
          <ul className="custom-scrollbar max-h-64 space-y-1.5 overflow-y-auto">
            {categories.map((category) => (
              <li
                key={category.id}
                className="flex flex-col gap-2 rounded-md border border-border px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
              >
                <span className="flex items-center gap-2 text-sm text-content">
                  {category.name}
                  <Badge tone={category.type === "INCOME" ? "success" : "neutral"}>{category.type}</Badge>
                </span>
                <button
                  onClick={() => removeCategory(category)}
                  className="text-content-subtle transition-colors hover:text-danger"
                  aria-label="Delete category"
                >
                  <Trash2 size={15} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Modal>
    </AppShell>
  );
}
