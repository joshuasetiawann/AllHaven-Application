"use client";

import { useEffect, useRef, useState } from "react";
import { AlarmClock, Flag, Pause, Play, Plus, RotateCcw, Timer as TimerIcon, Trash2, Watch } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/format";

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

const WORLD_CLOCKS: { city: string; tz: string }[] = [
  { city: "London", tz: "Europe/London" },
  { city: "New York", tz: "America/New_York" },
  { city: "Tokyo", tz: "Asia/Tokyo" },
  { city: "Sydney", tz: "Australia/Sydney" },
];

function LiveClock() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const tz = typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "";
  const city = tz ? (tz.split("/").pop() ?? tz).replace(/_/g, " ") : "";
  const tzAbbr = now
    ? new Intl.DateTimeFormat(undefined, { timeZoneName: "short" })
        .formatToParts(now)
        .find((p) => p.type === "timeZoneName")?.value ?? ""
    : "";

  const worldTime = (zone: string) =>
    now ? now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: zone }) : "--:--";
  const worldOffset = (zone: string) => {
    if (!now) return "";
    try {
      const there = new Date(now.toLocaleString("en-US", { timeZone: zone })).getTime();
      const here = new Date(now.toLocaleString("en-US")).getTime();
      const diff = Math.round(((there - here) / 3600000) * 2) / 2;
      if (diff === 0) return "±0h";
      return `${diff > 0 ? "+" : "−"}${Math.abs(diff)}h`;
    } catch {
      return "";
    }
  };

  return (
    <>
      <Card gradient padding="none" className="mb-5 p-[30px] text-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary-bright">
          {city ? `${city}${tzAbbr ? ` · ${tzAbbr}` : ""}` : "Local time"}
        </p>
        <p className="glow-text mt-2.5 font-mono text-5xl font-semibold leading-none tabular-nums text-content sm:text-[64px] sm:tracking-[-0.02em]">
          {now ? `${pad(now.getHours())}:${pad(now.getMinutes())}` : "--:--"}
          <span className="text-2xl text-content-subtle sm:text-[28px]">:{now ? pad(now.getSeconds()) : "--"}</span>
        </p>
        <p className="mt-3 text-sm text-content-muted">
          {now ? now.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" }) : " "}
        </p>
      </Card>
      <div className="mb-5 grid grid-cols-2 gap-3.5 md:grid-cols-4">
        {WORLD_CLOCKS.map((w) => (
          <div key={w.tz} className="glass-tile p-4">
            <p className="text-[12.5px] text-content-muted">{w.city}</p>
            <p className="mt-1.5 font-mono text-[22px] tabular-nums text-content">{worldTime(w.tz)}</p>
            <p className="mt-[3px] text-[11px] text-content-faint">{worldOffset(w.tz)}</p>
          </div>
        ))}
      </div>
    </>
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
    <Card padding="none" className="p-[22px] text-center">
      <div className="mb-3.5 flex items-center justify-center gap-2">
        <Watch size={16} className="text-secondary-soft" />
        <span className="text-[13px] font-semibold text-content">Stopwatch</span>
      </div>
      <p className="font-mono text-[40px] font-semibold leading-none tabular-nums text-content">
        {pad(Math.floor(elapsed / 60000))}:{pad(Math.floor((elapsed % 60000) / 1000))}
        <span className="text-[22px] text-content-subtle">.{pad(Math.floor((elapsed % 1000) / 10))}</span>
      </p>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-2.5">
        <Button onClick={() => setRunning((r) => !r)} className="px-[18px]">
          {running ? <><Pause size={14} className="mr-1.5" /> Pause</> : <><Play size={14} className="mr-1.5" /> Start</>}
        </Button>
        <Button variant="ghost" onClick={() => setLaps((l) => [elapsed, ...l])} disabled={!running}>
          <Flag size={14} className="mr-1.5" /> Lap
        </Button>
        <Button variant="ghost" onClick={() => { setRunning(false); setElapsed(0); setLaps([]); }}>
          <RotateCcw size={14} className="mr-1.5" /> Reset
        </Button>
      </div>
      {laps.length ? (
        <ul className="custom-scrollbar mx-auto mt-5 max-h-48 w-full max-w-xs space-y-1.5 overflow-y-auto text-left">
          {laps.map((l, i) => (
            <li key={i} className="glass-tile flex justify-between rounded-md px-3 py-1.5 text-sm">
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-content-subtle">Lap {laps.length - i}</span>
              <span className="font-mono tabular-nums text-content">{fmt(l)}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
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
    <label className="flex flex-col items-center gap-1.5">
      <input
        type="number" min={0} max={max} value={val} disabled={running}
        onChange={(e) => set(Math.max(0, Math.min(max, Number(e.target.value) || 0)))}
        className="glass-tile h-12 w-16 rounded-md text-center font-mono text-lg tabular-nums text-content focus:border-primary/60 focus:outline-none disabled:opacity-60"
      />
      <span className="label-mono">{label}</span>
    </label>
  );

  return (
    <Card padding="none" className="p-[22px] text-center">
      <div className="mb-3.5 flex items-center justify-center gap-2">
        <TimerIcon size={16} className="text-primary-bright" />
        <span className="text-[13px] font-semibold text-content">Timer</span>
      </div>
      {remaining > 0 || running ? (
        <p className={cn("font-mono text-[40px] font-semibold leading-none tabular-nums", done ? "text-warning" : "text-content")}>{disp}</p>
      ) : (
        <div className="flex items-end justify-center gap-2">
          {numField(h, setH, 99, "hrs")}<span className="pb-7 font-mono text-2xl text-content-subtle">:</span>
          {numField(m, setM, 59, "min")}<span className="pb-7 font-mono text-2xl text-content-subtle">:</span>
          {numField(s, setS, 59, "sec")}
        </div>
      )}
      {done ? <p className="mt-3 text-sm font-medium text-warning">Time&apos;s up!</p> : null}
      <div className="mt-4 flex flex-wrap items-center justify-center gap-2.5">
        {!running ? (
          <Button onClick={start} className="px-[18px]"><Play size={14} className="mr-1.5" /> Start</Button>
        ) : (
          <Button onClick={() => setRunning(false)} className="px-[18px]"><Pause size={14} className="mr-1.5" /> Pause</Button>
        )}
        <Button variant="ghost" onClick={reset}><RotateCcw size={14} className="mr-1.5" /> Reset</Button>
      </div>
    </Card>
  );
}

type Alarm = { id: string; time: string; label: string; enabled: boolean };

function Alarms() {
  const toast = useToast();
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
          toast.warning("Alarm", `${a.label ? `${a.label} · ` : ""}${a.time}`);
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
    <Card padding="none" className="mt-4 p-[22px]">
      <CardHeader
        icon={<AlarmClock size={16} />}
        title="Alarms"
        subtitle="Alarms are saved in your browser and ring while AllHaven is open."
      />
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-end">
        <label className="flex flex-col gap-1.5">
          <span className="label-mono">Time</span>
          <input type="time" value={time} onChange={(e) => setTime(e.target.value)}
            className="glass-tile h-11 rounded-md px-3 font-mono tabular-nums text-content focus:border-primary/60 focus:outline-none" />
        </label>
        <label className="flex flex-1 flex-col gap-1.5">
          <span className="label-mono">Label (optional)</span>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Wake up, meeting…"
            className="glass-tile h-11 rounded-md px-3 text-content placeholder:text-content-subtle focus:border-primary/60 focus:outline-none" />
        </label>
        <Button onClick={add} className="px-4"><Plus size={15} className="mr-1.5" /> Add</Button>
      </div>

      <ul className="mt-5 space-y-2">
        {alarms.length === 0 ? (
          <li className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-sm text-content-subtle">
            No alarms yet. Alarms ring while this page is open.
          </li>
        ) : alarms.map((a) => (
          <li key={a.id} className="glass-tile flex items-center gap-3 px-3.5 py-2.5">
            <span className="font-mono text-xl tabular-nums text-content">{a.time}</span>
            {a.label ? <span className="min-w-0 flex-1 truncate text-sm text-content-muted">{a.label}</span> : <span className="flex-1" />}
            <button
              type="button"
              onClick={() => setAlarms((p) => p.map((x) => (x.id === a.id ? { ...x, enabled: !x.enabled } : x)))}
              className={cn(
                "relative h-5 w-9 rounded-full transition-all",
                a.enabled
                  ? "bg-[linear-gradient(90deg,rgb(var(--color-primary)),rgb(var(--color-secondary)))] shadow-toggle-on"
                  : "bg-white/10",
              )}
              aria-label="Toggle alarm"
            >
              <span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform", a.enabled ? "translate-x-4" : "translate-x-0.5")} />
            </button>
            <button type="button" onClick={() => setAlarms((p) => p.filter((x) => x.id !== a.id))}
              className="text-content-subtle transition-colors hover:text-danger" aria-label="Delete alarm">
              <Trash2 size={16} />
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-3 font-mono text-[11px] text-content-faint">
        Foundation: alarms are saved in your browser and ring while AllHaven is open. Background/push alarms come later.
      </p>
    </Card>
  );
}

export default function ClockPage() {
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl">
        <div className="mb-5">
          <h1 className="text-[30px] font-semibold tracking-[-0.02em] text-content">Clock</h1>
          <p className="mt-2 text-[13.5px] text-content-muted">World clocks, timer, stopwatch, and alarms.</p>
        </div>
        <LiveClock />
        <div className="grid gap-4 lg:grid-cols-2">
          <CountdownTimer />
          <Stopwatch />
        </div>
        <Alarms />
      </div>
    </AppShell>
  );
}
