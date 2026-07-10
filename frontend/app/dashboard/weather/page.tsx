"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CloudSun, Droplets, MapPin, Plus, Settings, Thermometer, Trash2, Wind } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Toggle } from "@/components/ui/Toggle";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { weatherApi, ApiException } from "@/lib/api";
import type { WeatherCurrent, WeatherLocation } from "@/types";

export default function WeatherPage() {
  const [current, setCurrent] = useState<WeatherCurrent | null>(null);
  const [locations, setLocations] = useState<WeatherLocation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loadingWeather, setLoadingWeather] = useState(false);
  const [name, setName] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [adding, setAdding] = useState(false);

  const loadWeather = async (location?: string) => {
    setLoadingWeather(true);
    setActionError(null);
    try {
      setCurrent(await weatherApi.current(location));
    } catch (err) {
      setActionError(err instanceof ApiException ? err.message : "Failed to load weather.");
    } finally {
      setLoadingWeather(false);
    }
  };

  const load = async () => {
    setError(null);
    try {
      const [cur, locs] = await Promise.all([
        weatherApi.current(),
        weatherApi.listLocations(),
      ]);
      setCurrent(cur);
      setLocations(locs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load weather.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const addLocation = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setAdding(true);
    setActionError(null);
    try {
      await weatherApi.addLocation(name.trim(), isDefault);
      setName("");
      setIsDefault(false);
      setLocations(await weatherApi.listLocations());
    } catch (err) {
      setActionError(err instanceof ApiException ? err.message : "Could not add location.");
    } finally {
      setAdding(false);
    }
  };

  const removeLocation = async (loc: WeatherLocation) => {
    setActionError(null);
    setLocations((prev) => prev?.filter((l) => l.id !== loc.id) ?? prev);
    try {
      await weatherApi.removeLocation(loc.id);
    } catch (err) {
      setActionError(err instanceof ApiException ? err.message : "Could not remove location.");
      setLocations(await weatherApi.listLocations().catch(() => locations ?? []));
    }
  };

  const renderWeather = () => {
    if (loadingWeather) return <Loading />;
    if (!current) return null;

    if (current.status === "setup_required") {
      return (
        <Card>
          <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
            <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-warning/30 bg-warning/10 text-warning">
              <Settings size={22} />
            </span>
            <p className="text-sm font-medium text-content">Weather setup required</p>
            <p className="mt-1 max-w-sm text-[13px] text-content-muted">
              {current.detail || "Add a Weather API key in Settings → Connected Tools to enable live weather."}
            </p>
            <Link href="/dashboard/settings" className="mt-4">
              <Button variant="ghost" size="sm">
                <Settings size={14} /> Open Settings → Connected Tools
              </Button>
            </Link>
          </div>
        </Card>
      );
    }

    if (current.status === "no_location") {
      return (
        <EmptyState
          title="No location set"
          description={current.detail || "Add a location below to see current weather."}
          icon={<MapPin size={20} />}
        />
      );
    }

    if (current.status === "ok") {
      return (
        <Card padding="lg">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface-input text-primary">
                <CloudSun size={22} />
              </span>
              <div>
                <p className="label-mono">Current weather</p>
                <h2 className="mt-0.5 text-lg font-semibold text-content">
                  {current.location ?? "—"}
                </h2>
              </div>
            </div>
            {typeof current.temp_c === "number" ? (
              <p className="text-3xl font-semibold text-content">{Math.round(current.temp_c)}°C</p>
            ) : null}
          </div>

          {current.description ? (
            <p className="mt-4 text-sm capitalize text-content-muted">{current.description}</p>
          ) : null}

          <div className="mt-5 grid grid-cols-1 gap-3 border-t border-border pt-5 sm:grid-cols-3">
            {typeof current.feels_like_c === "number" ? (
              <div className="flex items-center gap-2 text-[13px] text-content-muted">
                <Thermometer size={15} className="text-content-subtle" />
                Feels like {Math.round(current.feels_like_c)}°C
              </div>
            ) : null}
            {typeof current.humidity === "number" ? (
              <div className="flex items-center gap-2 text-[13px] text-content-muted">
                <Droplets size={15} className="text-content-subtle" />
                Humidity {current.humidity}%
              </div>
            ) : null}
            {typeof current.wind_speed === "number" ? (
              <div className="flex items-center gap-2 text-[13px] text-content-muted">
                <Wind size={15} className="text-content-subtle" />
                Wind {current.wind_speed} m/s
              </div>
            ) : null}
          </div>
        </Card>
      );
    }

    // unsupported_provider | unavailable | error
    return (
      <ErrorState
        message={current.detail || "Weather is currently unavailable."}
        onRetry={() => loadWeather()}
      />
    );
  };

  return (
    <AppShell>
      <PageHeader title="Weather" subtitle="Live weather context for your saved locations." />

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !current || !locations ? (
        <Loading />
      ) : (
        <>
          {actionError ? (
            <div className="mb-4">
              <ErrorState message={actionError} />
            </div>
          ) : null}

          <div className="mb-5">{renderWeather()}</div>

          <Card className="mb-5">
            <form onSubmit={addLocation} className="space-y-4">
              <Input
                id="location-name"
                label="Add a saved location"
                leftIcon={<MapPin size={15} />}
                placeholder="e.g. Jakarta"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-[13px] text-content-muted">
                  <Toggle checked={isDefault} onChange={setIsDefault} label="Set as default" />
                  Set as default
                </label>
                <Button type="submit" loading={adding} disabled={!name.trim()}>
                  <Plus size={16} /> Add location
                </Button>
              </div>
            </form>
          </Card>

          {locations.length === 0 ? (
            <EmptyState
              title="No saved locations"
              description="Add a location above to track its weather."
              icon={<MapPin size={20} />}
            />
          ) : (
            <div className="space-y-2.5">
              {locations.map((loc) => (
                <Card key={loc.id} className="p-4" hover>
                  <div className="flex items-center justify-between gap-3">
                    <button
                      onClick={() => loadWeather(loc.name)}
                      className="flex min-w-0 items-center gap-3 text-left"
                    >
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
                        <MapPin size={16} />
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-content">{loc.name}</p>
                        <p className="mt-0.5 text-[12px] text-content-subtle">View weather</p>
                      </div>
                    </button>
                    <div className="flex shrink-0 items-center gap-2">
                      {loc.is_default ? <Badge tone="primary">Default</Badge> : null}
                      <button
                        onClick={() => removeLocation(loc)}
                        className="rounded-md p-2 text-content-subtle transition-colors hover:text-danger"
                        aria-label="Remove location"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </AppShell>
  );
}
