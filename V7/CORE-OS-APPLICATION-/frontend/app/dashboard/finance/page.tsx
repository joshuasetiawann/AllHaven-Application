"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownLeft, ArrowUpRight, Plus, SlidersHorizontal, Trash2, Wallet } from "lucide-react";
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
import { financeApi, ApiException } from "@/lib/api";
import { formatCurrency, formatDate, monthLabel } from "@/lib/format";
import type { FinanceCategory, FinanceSummary, FinanceType, Transaction } from "@/types";

const todayIso = () => new Date().toISOString().slice(0, 10);

export default function FinancePage() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  const [categories, setCategories] = useState<FinanceCategory[]>([]);
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
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
      const [cats, txns, sum] = await Promise.all([
        financeApi.listCategories(),
        financeApi.listTransactions(),
        financeApi.summary(year, month),
      ]);
      setCategories(cats);
      setTransactions(txns);
      setSummary(sum);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load finance data.");
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const weeklyBars = useMemo(() => {
    const buckets = [0, 0, 0, 0, 0];
    (transactions ?? []).forEach((t) => {
      const d = new Date(t.transaction_date);
      if (d.getFullYear() === year && d.getMonth() + 1 === month && t.type === "EXPENSE") {
        buckets[Math.min(4, Math.floor((d.getDate() - 1) / 7))] += t.amount;
      }
    });
    return buckets.map((value, i) => ({ label: `W${i + 1}`, value }));
  }, [transactions, month, year]);

  const createTransaction = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await financeApi.createTransaction({
        type: txnForm.type,
        amount: Number(txnForm.amount),
        category_id: txnForm.category_id || null,
        description: txnForm.description || null,
        transaction_date: txnForm.transaction_date,
      });
      setTxnOpen(false);
      setTxnForm({ type: "EXPENSE", amount: "", category_id: "", description: "", transaction_date: todayIso() });
      await load();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to create transaction.");
    } finally {
      setSaving(false);
    }
  };

  const createCategory = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await financeApi.createCategory({ name: catForm.name, type: catForm.type });
      setCatForm({ name: "", type: "EXPENSE" });
      await load();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to create category.");
    } finally {
      setSaving(false);
    }
  };

  const removeTransaction = async (txn: Transaction) => {
    setTransactions((prev) => prev?.filter((t) => t.id !== txn.id) ?? prev);
    try {
      await financeApi.removeTransaction(txn.id);
      await load();
    } catch {
      void load();
    }
  };

  const removeCategory = async (category: FinanceCategory) => {
    setCategories((prev) => prev.filter((c) => c.id !== category.id));
    try {
      await financeApi.removeCategory(category.id);
    } catch {
      void load();
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Finance"
        subtitle={`Cashflow overview · ${monthLabel(year, month)}`}
        actions={
          <>
            <Button variant="ghost" onClick={() => setCatOpen(true)}>
              <SlidersHorizontal size={15} /> Categories
            </Button>
            <Button onClick={() => setTxnOpen(true)}>
              <Plus size={16} /> New transaction
            </Button>
          </>
        }
      />

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !transactions || !summary ? (
        <Loading />
      ) : (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <Card padding="md">
              <p className="label-mono">Income</p>
              <p className="mt-1.5 text-2xl font-semibold text-success">
                {formatCurrency(summary.total_income, summary.currency)}
              </p>
            </Card>
            <Card padding="md">
              <p className="label-mono">Expense</p>
              <p className="mt-1.5 text-2xl font-semibold text-danger">
                {formatCurrency(summary.total_expense, summary.currency)}
              </p>
            </Card>
            <Card padding="md" className="border-primary/20">
              <p className="label-mono">Balance</p>
              <p className="mt-1.5 text-2xl font-semibold text-content">
                {formatCurrency(summary.balance, summary.currency)}
              </p>
            </Card>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader title="Transactions" subtitle={`${summary.transaction_count} this month`} icon={<Wallet size={18} />} />
              {transactions.length === 0 ? (
                <EmptyState
                  title="No transactions yet"
                  description="Record income or expenses to build your monthly summary."
                />
              ) : (
                <ul className="divide-y divide-border">
                  {transactions.map((txn) => {
                    const income = txn.type === "INCOME";
                    return (
                      <li key={txn.id} className="flex items-center justify-between gap-4 py-3">
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
                              {txn.category_name_snapshot ? ` · ${txn.category_name_snapshot}` : ""}
                            </p>
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <span className={"text-sm font-semibold " + (income ? "text-success" : "text-danger")}>
                            {income ? "+" : "−"}
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
              <CardHeader title="Weekly spend" subtitle={monthLabel(year, month)} icon={<Wallet size={18} />} />
              <BarChart data={weeklyBars} height={140} />
              <p className="mt-4 border-t border-border pt-3 text-[12px] text-content-subtle">
                CoreOS tracks cashflow. It does not provide financial advice.
              </p>
            </Card>
          </div>
        </div>
      )}

      {/* New transaction modal */}
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
          <div className="grid grid-cols-2 gap-3">
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

      {/* Categories modal */}
      <Modal open={catOpen} onClose={() => setCatOpen(false)} title="Categories">
        <form onSubmit={createCategory} className="mb-4 grid grid-cols-[1fr_auto_auto] items-end gap-2">
          <Input
            id="cat-name"
            label="New category"
            placeholder="Salary, Food…"
            value={catForm.name}
            onChange={(e) => setCatForm({ ...catForm, name: e.target.value })}
          />
          <Select
            value={catForm.type}
            onChange={(e) => setCatForm({ ...catForm, type: e.target.value as FinanceType })}
            className="w-28"
          >
            <option value="EXPENSE">Expense</option>
            <option value="INCOME">Income</option>
          </Select>
          <Button type="submit" loading={saving} disabled={!catForm.name.trim()}>
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
                className="flex items-center justify-between rounded-md border border-border px-3 py-2"
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
