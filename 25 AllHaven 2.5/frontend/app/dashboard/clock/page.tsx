"use client";

import { useEffect, useRef, useState } from "react";
import { AlarmClock, Clock as ClockIcon, Flag, Pause, Play, Plus, RotateCcw, Timer as TimerIcon, Trash2 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/format";

type Tab = "clock" | "stopwatch" | "timer" | "alarm";

const pad = (n: number) => String(n).padStart(2, "0");

// Short beep via WebAudio (no asset needed). Best-effort; silent if unavailable.
function beep(ms = 600) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Ctx = window.AudioContext || (window as any).webkitAudioContext;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 880;
    osc.connect(gain);
    gain.connect(ctx.destination);
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    osc.start();
    osc.stop(ctx.currentTime + ms / 1000);
    osc.onended = () => ctx.close();
  } catch {
    /* audio not available */
  }
}

function LiveClock() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const tz = typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "";
  return (
    <div className="flex flex-col items-center py-8 text-center">
      <p className="font-mono text-5xl font-semibold tabular-nums text-content sm:text-7xl">
        {now ? now.toLocaleTimeString(undefined, { hour12: false }) : "--:--:--"}
      </p>
      <p className="mt-3 text-sm text-content-muted sm:text-base">
        {now ? now.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" }) : ""}
      </p>
      {tz ? <p className="mt-1 text-[12px] text-content-subtle">{tz}</p> : null}
    </div>
  );
}

function Stopwatch() {
  const [elapsed, setElapsed] = useState(0);
  const [running, setRunning] = useState(false);
  const [laps, setLaps] = useState<number[]>([]);
  const startRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!running) return;
    startRef.current = performance.now() - elapsed;
    const tick = () => {
      setElapsed(performance.now() - startRef.current);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  const fmt = (ms: number) =>
    `${pad(Math.floor(ms / 60000))}:${pad(Math.floor((ms % 60000) / 1000))}.${pad(Math.floor((ms % 1000) / 10))}`;

  return (
    <div className="flex flex-col items-center py-8">
      <p className="font-mono text-5xl font-semibold tabular-nums text-content sm:text-6xl">{fmt(elapsed)}</p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        <Button onClick={() => setRunning((r) => !r)} className="px-5">
          {running ? <><Pause size={15} className="mr-1.5" /> Pause</> : <><Play size={15} className="mr-1.5" /> Start</>}
        </Button>
        <Button variant="secondary" onClick={() => setLaps((l) => [elapsed, ...l])} disabled={!running}>
          <Flag size={15} className="mr-1.5" /> Lap
        </Button>
        <Button variant="ghost" onClick={() => { setRunning(false); setElapsed(0); setLaps([]); }}>
          <RotateCcw size={15} className="mr-1.5" /> Reset
        </Button>
      </div>
      {laps.length ? (
        <ul className="custom-scrollbar mt-6 max-h-48 w-full max-w-xs space-y-1 overflow-y-auto">
          {laps.map((l, i) => (
            <li key={i} className="flex justify-between rounded-md border border-border bg-surface-input px-3 py-1.5 text-sm">
              <span className="text-content-subtle">Lap {laps.length - i}</span>
              <span className="font-mono tabular-nums text-content">{fmt(l)}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function CountdownTimer() {
  const [h, setH] = useState(0);
  const [m, setM] = useState(5);
  const [s, setS] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const endRef = useRef(0);

  useEffect(() => {
    if (!running) return;
    endRef.current = performance.now() + remaining;
    const id = setInterval(() => {
      const left = Math.max(0, endRef.current - performance.now());
      setRemaining(left);
      if (left <= 0) { setRunning(false); setDone(true); beep(900); }
    }, 200);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  const start = () => {
    const total = (h * 3600 + m * 60 + s) * 1000;
    if (total <= 0) return;
    setRemaining(total); setDone(false); setRunning(true);
  };
  const reset = () => { setRunning(false); setRemaining(0); setDone(false); };
  const left = remaining || (h * 3600 + m * 60 + s) * 1000;
  const disp = `${pad(Math.floor(left / 3600000))}:${pad(Math.floor((left % 3600000) / 60000))}:${pad(Math.floor((left % 60000) / 1000))}`;
  const numField = (val: number, set: (n: number) => void, max: number, label: string) => (
    <label className="flex flex-col items-center gap-1">
      <input
        type="number" min={0} max={max} value={val} disabled={running}
        onChange={(e) => set(Math.max(0, Math.min(max, Number(e.target.value) || 0)))}
        className="h-12 w-16 rounded-lg border border-border bg-surface-input text-center text-lg text-content focus:border-primary/70 focus:outline-none disabled:opacity-60"
      />
      <span className="text-[11px] uppercase tracking-wide text-content-subtle">{label}</span>
    </label>
  );

  return (
    <div className="flex flex-col items-center py-8">
      {remaining > 0 || running ? (
        <p className={cn("font-mono text-5xl font-semibold tabular-nums sm:text-6xl", done ? "text-warning" : "text-content")}>{disp}</p>
      ) : (
        <div className="flex items-end gap-2">
          {numField(h, setH, 99, "hrs")}<span className="pb-6 text-2xl text-content-subtle">:</span>
          {numField(m, setM, 59, "min")}<span className="pb-6 text-2xl text-content-subtle">:</span>
          {numField(s, setS, 59, "sec")}
        </div>
      )}
      {done ? <p className="mt-3 text-sm font-medium text-warning">Time&apos;s up!</p> : null}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        {!running ? (
          <Button onClick={start} className="px-5"><Play size={15} className="mr-1.5" /> Start</Button>
        ) : (
          <Button onClick={() => setRunning(false)} className="px-5"><Pause size={15} className="mr-1.5" /> Pause</Button>
        )}
        <Button variant="ghost" onClick={reset}><RotateCcw size={15} className="mr-1.5" /> Reset</Button>
      </div>
    </div>
  );
}

type Alarm = { id: string; time: string; label: string; enabled: boolean };

function Alarms() {
  const [alarms, setAlarms] = useState<Alarm[]>([]);
  const [time, setTime] = useState("07:00");
  const [label, setLabel] = useState("");
  const firedRef = useRef<Record<string, string>>({});

  useEffect(() => {
    try { const raw = localStorage.getItem("allhaven.alarms"); if (raw) setAlarms(JSON.parse(raw)); } catch { /* ignore */ }
  }, []);
  useEffect(() => {
    try { localStorage.setItem("allhaven.alarms", JSON.stringify(alarms)); } catch { /* ignore */ }
  }, [alarms]);
  useEffect(() => {
    const id = setInterval(() => {
      const now = new Date();
      const hhmm = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
      const minuteKey = `${now.toDateString()} ${hhmm}`;
      for (const a of alarms) {
        if (a.enabled && a.time === hhmm && firedRef.current[a.id] !== minuteKey) {
          firedRef.current[a.id] = minuteKey;
          beep(1000);
          window.alert(`⏰ Alarm${a.label ? `: ${a.label}` : ""} — ${a.time}`);
        }
      }
    }, 1000);
    return () => clearInterval(id);
  }, [alarms]);

  const add = () => {
    if (!time) return;
    setAlarms((p) => [...p, { id: crypto.randomUUID(), time, label: label.trim(), enabled: true }].sort((a, b) => a.time.localeCompare(b.time)));
    setLabel("");
  };

  return (
    <div className="py-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <label className="flex flex-col gap-1">
          <span className="text-[11px] uppercase tracking-wide text-content-subtle">Time</span>
          <input type="time" value={time} onChange={(e) => setTime(e.target.value)}
            className="h-11 rounded-lg border border-border bg-surface-input px-3 text-content focus:border-primary/70 focus:outline-none" />
        </label>
        <label className="flex flex-1 flex-col gap-1">
          <span className="text-[11px] uppercase tracking-wide text-content-subtle">Label (optional)</span>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Wake up, meeting…"
            className="h-11 rounded-lg border border-border bg-surface-input px-3 text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none" />
        </label>
        <Button onClick={add} className="px-4"><Plus size={16} className="mr-1.5" /> Add</Button>
      </div>

      <ul className="mt-5 space-y-2">
        {alarms.length === 0 ? (
          <li className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-content-subtle">
            No alarms yet. Alarms ring while this page is open.
          </li>
        ) : alarms.map((a) => (
          <li key={a.id} className="flex items-center gap-3 rounded-lg border border-border bg-surface-input px-3.5 py-2.5">
            <span className="font-mono text-xl tabular-nums text-content">{a.time}</span>
            {a.label ? <span className="min-w-0 flex-1 truncate text-sm text-content-muted">{a.label}</span> : <span className="flex-1" />}
            <button
              type="button"
              onClick={() => setAlarms((p) => p.map((x) => (x.id === a.id ? { ...x, enabled: !x.enabled } : x)))}
              className={cn("relative h-5 w-9 rounded-full transition-colors", a.enabled ? "bg-primary" : "bg-surface-high")}
              aria-label="Toggle alarm"
            >
              <span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform", a.enabled ? "translate-x-4" : "translate-x-0.5")} />
            </button>
            <button type="button" onClick={() => setAlarms((p) => p.filter((x) => x.id !== a.id))}
              className="text-content-subtle hover:text-danger" aria-label="Delete alarm">
              <Trash2 size={16} />
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] text-content-subtle">
        Foundation: alarms are saved in your browser and ring while AllHaven is open. Background/push alarms come later.
      </p>
    </div>
  );
}

const TABS: { id: Tab; label: string; icon: typeof ClockIcon }[] = [
  { id: "clock", label: "Clock", icon: ClockIcon },
  { id: "stopwatch", label: "Stopwatch", icon: TimerIcon },
  { id: "timer", label: "Timer", icon: TimerIcon },
  { id: "alarm", label: "Alarm", icon: AlarmClock },
];

export default function ClockPage() {
  const [tab, setTab] = useState<Tab>("clock");
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-lg">
        <h1 className="mb-4 text-lg font-semibold text-content">Clock</h1>
        <div className="inline-flex w-full flex-wrap gap-1 rounded-xl border border-border bg-surface-input p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-[13px] transition-colors",
                tab === t.id ? "bg-surface-high text-content" : "text-content-muted hover:text-content",
              )}
            >
              <t.icon size={14} /> {t.label}
            </button>
          ))}
        </div>
        <div className="mt-4 rounded-2xl border border-border bg-surface/40 px-4 sm:px-6">
          {tab === "clock" ? <LiveClock /> : tab === "stopwatch" ? <Stopwatch /> : tab === "timer" ? <CountdownTimer /> : <Alarms />}
        </div>
      </div>
    </AppShell>
  );
}
