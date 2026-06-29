"use client";

import { useEffect, useState } from "react";
import { Delete } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { cn } from "@/lib/format";

const OPS: Record<string, (a: number, b: number) => number> = {
  "+": (a, b) => a + b,
  "−": (a, b) => a - b,
  "×": (a, b) => a * b,
  "÷": (a, b) => a / b,
};

// Trim floating-point noise (0.1 + 0.2) and overlong results.
function fmt(n: number): string {
  if (!isFinite(n)) return "Error";
  return Number(n.toPrecision(12)).toString();
}

export default function CalculatorPage() {
  const [display, setDisplay] = useState("0");
  const [acc, setAcc] = useState<number | null>(null);
  const [op, setOp] = useState<string | null>(null);
  const [overwrite, setOverwrite] = useState(true); // next digit starts a new number
  const [expr, setExpr] = useState(""); // small "history" line above the display

  const inputDigit = (d: string) => {
    setDisplay((cur) => {
      if (overwrite || cur === "0") return d;
      if (cur.replace(/[^0-9]/g, "").length >= 15) return cur;
      return cur + d;
    });
    setOverwrite(false);
  };
  const inputDot = () => {
    setDisplay((cur) => (overwrite ? "0." : cur.includes(".") ? cur : cur + "."));
    setOverwrite(false);
  };
  const clearAll = () => { setDisplay("0"); setAcc(null); setOp(null); setOverwrite(true); setExpr(""); };
  const backspace = () => {
    if (overwrite) return;
    setDisplay((cur) => (cur.length <= 1 || (cur.length === 2 && cur.startsWith("-")) ? "0" : cur.slice(0, -1)));
  };
  const percent = () => { setDisplay((cur) => fmt(parseFloat(cur) / 100)); setOverwrite(true); };
  const toggleSign = () =>
    setDisplay((cur) => (cur.startsWith("-") ? cur.slice(1) : cur === "0" ? cur : "-" + cur));

  const chooseOp = (nextOp: string) => {
    const value = parseFloat(display);
    if (acc == null) {
      setAcc(value);
    } else if (op && !overwrite) {
      const r = OPS[op](acc, value);
      setAcc(r);
      setDisplay(fmt(r));
    }
    setOp(nextOp);
    setOverwrite(true);
    setExpr(`${fmt(acc == null || overwrite ? value : OPS[op!](acc, value))} ${nextOp}`);
  };

  const equals = () => {
    if (op == null || acc == null) return;
    const value = parseFloat(display);
    const r = OPS[op](acc, value);
    setExpr(`${fmt(acc)} ${op} ${fmt(value)} =`);
    setDisplay(fmt(r));
    setAcc(null);
    setOp(null);
    setOverwrite(true);
  };

  // Keyboard support (re-subscribes on state change so values stay fresh).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const k = e.key;
      if (k >= "0" && k <= "9") inputDigit(k);
      else if (k === ".") inputDot();
      else if (k === "+") chooseOp("+");
      else if (k === "-") chooseOp("−");
      else if (k === "*") chooseOp("×");
      else if (k === "/") { e.preventDefault(); chooseOp("÷"); }
      else if (k === "%") percent();
      else if (k === "Enter" || k === "=") { e.preventDefault(); equals(); }
      else if (k === "Backspace") backspace();
      else if (k === "Escape") clearAll();
      else return;
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  type Btn = { label: React.ReactNode; on: () => void; variant?: "num" | "op" | "accent" | "muted" | "clear"; wide?: boolean; active?: boolean };
  const buttons: Btn[] = [
    { label: "AC", on: clearAll, variant: "clear" },
    { label: <Delete size={18} />, on: backspace, variant: "muted" },
    { label: "%", on: percent, variant: "muted" },
    { label: "÷", on: () => chooseOp("÷"), variant: "op", active: op === "÷" },
    { label: "7", on: () => inputDigit("7"), variant: "num" },
    { label: "8", on: () => inputDigit("8"), variant: "num" },
    { label: "9", on: () => inputDigit("9"), variant: "num" },
    { label: "×", on: () => chooseOp("×"), variant: "op", active: op === "×" },
    { label: "4", on: () => inputDigit("4"), variant: "num" },
    { label: "5", on: () => inputDigit("5"), variant: "num" },
    { label: "6", on: () => inputDigit("6"), variant: "num" },
    { label: "−", on: () => chooseOp("−"), variant: "op", active: op === "−" },
    { label: "1", on: () => inputDigit("1"), variant: "num" },
    { label: "2", on: () => inputDigit("2"), variant: "num" },
    { label: "3", on: () => inputDigit("3"), variant: "num" },
    { label: "+", on: () => chooseOp("+"), variant: "op", active: op === "+" },
    { label: "±", on: toggleSign, variant: "num" },
    { label: "0", on: () => inputDigit("0"), variant: "num" },
    { label: ".", on: inputDot, variant: "num" },
    { label: "=", on: equals, variant: "accent" },
  ];

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-sm">
        <div className="mb-5">
          <h1 className="text-[30px] font-semibold tracking-[-0.02em] text-content">Calculator</h1>
          <p className="mt-2 text-[13.5px] text-content-muted">Quick math, keyboard-ready.</p>
        </div>
        <div className="panel rounded-[22px] p-4 sm:p-5">
          {/* Display */}
          <div className="mb-4 rounded-xl border border-white/[0.08] bg-bg-deep/60 px-[18px] py-4 text-right">
            <p className="h-4 truncate font-mono text-[12px] text-content-subtle">{expr}&nbsp;</p>
            <p className="mt-1.5 break-all font-mono text-3xl font-semibold tabular-nums text-content [text-shadow:0_0_24px_rgb(var(--color-primary)/0.25)] sm:text-[32px]">{display}</p>
          </div>
          {/* Keypad */}
          <div className="grid grid-cols-4 gap-2 sm:gap-2.5">
            {buttons.map((b, i) => (
              <button
                key={i}
                type="button"
                onClick={b.on}
                className={cn(
                  "flex h-14 select-none items-center justify-center rounded-lg text-[17px] font-medium transition-all sm:h-[52px]",
                  b.variant === "accent" &&
                    "grad-primary border-0 text-lg text-primary-fg shadow-[0_0_18px_rgb(var(--color-primary)/0.4)] hover:brightness-[1.06]",
                  b.variant === "op" &&
                    cn(
                      "border text-lg text-primary-bright",
                      b.active
                        ? "border-[rgb(var(--color-primary)/0.5)] bg-[rgb(var(--color-primary)/0.22)]"
                        : "border-[rgb(var(--color-primary)/0.3)] bg-[rgb(var(--color-primary)/0.12)] hover:bg-[rgb(var(--color-primary)/0.18)]",
                    ),
                  b.variant === "clear" &&
                    "border border-white/10 bg-[rgb(var(--color-danger)/0.08)] text-base text-danger hover:bg-[rgb(var(--color-danger)/0.14)]",
                  b.variant === "muted" &&
                    "border border-white/10 bg-white/[0.03] text-base text-content-muted hover:bg-white/[0.06] hover:text-content",
                  (b.variant === "num" || !b.variant) &&
                    "border border-white/10 bg-white/[0.03] text-content hover:bg-white/[0.06]",
                )}
              >
                {b.label}
              </button>
            ))}
          </div>
        </div>
        <p className="mt-3 text-center text-[11px] text-content-subtle">
          Tip: use your keyboard — digits, <span className="text-content-muted">+ − * /</span>, %, Enter, Backspace, Esc.
        </p>
      </div>
    </AppShell>
  );
}
