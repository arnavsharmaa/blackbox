"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { IncidentSummary } from "@blackbox/schemas";
import { fetchIncidents } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import {
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  OUTCOME_LABELS,
  OUTCOME_STYLES,
  SEVERITY_STYLES,
  confidencePct,
  formatDateTime,
  formatDuration,
} from "@/lib/format";
import {
  Badge,
  EmptyState,
  ErrorState,
  LoadingState,
  StatCard,
} from "@/components/ui";
import type { FailureCategory } from "@blackbox/schemas";

interface Filters {
  robot_id: string;
  severity: string;
  failure_category: string;
  outcome: string;
  start_after: string;
  q: string;
}

const EMPTY_FILTERS: Filters = {
  robot_id: "",
  severity: "",
  failure_category: "",
  outcome: "",
  start_after: "",
  q: "",
};

const PAGE_SIZE = 25;

export default function OverviewPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [searchText, setSearchText] = useState("");

  // Debounce free-text search so we don't refetch per keystroke.
  useEffect(() => {
    const handle = setTimeout(
      () => setFilters((current) => ({ ...current, q: searchText.trim() })),
      300,
    );
    return () => clearTimeout(handle);
  }, [searchText]);

  // Back to the first page whenever the filters change.
  const [offset, setOffset] = useState(0);
  useEffect(() => setOffset(0), [filters]);

  // One unfiltered fetch powers the fleet/stat panels; the filtered fetch
  // powers the table. Both are cheap against the local API.
  const all = useApi(() => fetchIncidents({ limit: 200 }), []);
  const filtered = useApi(
    () =>
      fetchIncidents({
        limit: PAGE_SIZE,
        offset,
        robot_id: filters.robot_id || undefined,
        severity: filters.severity || undefined,
        failure_category: filters.failure_category || undefined,
        outcome: filters.outcome || undefined,
        start_after: filters.start_after
          ? new Date(filters.start_after).toISOString()
          : undefined,
        q: filters.q || undefined,
      }),
    [filters, offset],
  );

  const stats = useMemo(() => {
    const items = all.data?.items ?? [];
    const critical = items.filter((i) => i.severity === "critical").length;
    const byCategory = new Map<FailureCategory, number>();
    for (const item of items) {
      if (item.failure_category) {
        byCategory.set(
          item.failure_category,
          (byCategory.get(item.failure_category) ?? 0) + 1,
        );
      }
    }
    const topCategory = [...byCategory.entries()].sort(
      (a, b) => b[1] - a[1],
    )[0];
    const robots = new Map<string, IncidentSummary[]>();
    for (const item of items) {
      const list = robots.get(item.robot_id) ?? [];
      list.push(item);
      robots.set(item.robot_id, list);
    }
    return { items, critical, byCategory, topCategory, robots };
  }, [all.data]);

  const robotIds = useMemo(
    () => [...stats.robots.keys()].sort(),
    [stats.robots],
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Incident overview</h1>
        <p className="mt-1 text-sm text-ink-dim">
          Recorded failures across the robot fleet, with deterministic root-cause
          analysis.
        </p>
      </div>

      {all.error ? (
        <ErrorState error={all.error} onRetry={all.refetch} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Total incidents"
              value={all.loading ? "…" : stats.items.length}
              sub="last 200 recorded"
            />
            <StatCard
              label="Critical incidents"
              value={all.loading ? "…" : stats.critical}
              accent={stats.critical > 0}
            />
            <StatCard
              label="Top failure category"
              value={
                all.loading
                  ? "…"
                  : stats.topCategory
                    ? CATEGORY_LABELS[stats.topCategory[0]]
                    : "—"
              }
              sub={
                stats.topCategory
                  ? `${stats.topCategory[1]} incident${stats.topCategory[1] === 1 ? "" : "s"}`
                  : undefined
              }
            />
            <StatCard
              label="Avg recovery attempts"
              value={all.loading ? "…" : avgRecoveries(stats.items)}
              sub="per failed navigation task"
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
            <div className="space-y-4">
              <FilterBar
                filters={filters}
                robotIds={robotIds}
                searchText={searchText}
                onSearch={setSearchText}
                onChange={setFilters}
                onClear={() => {
                  setSearchText("");
                  setFilters(EMPTY_FILTERS);
                }}
              />
              {filtered.error ? (
                <ErrorState error={filtered.error} onRetry={filtered.refetch} />
              ) : filtered.loading ? (
                <LoadingState label="Loading incidents…" />
              ) : filtered.data && filtered.data.items.length > 0 ? (
                <>
                  <IncidentTable items={filtered.data.items} />
                  <Pager
                    total={filtered.data.total}
                    offset={offset}
                    count={filtered.data.items.length}
                    onPage={setOffset}
                  />
                </>
              ) : (
                <EmptyState
                  title="No incidents match these filters"
                  hint="Clear one or more filters, or seed the demo data with `make seed`."
                />
              )}
            </div>
            <div className="space-y-6">
              <FleetPanel robots={stats.robots} loading={all.loading} />
              <CategoryBreakdown
                byCategory={stats.byCategory}
                total={stats.items.length}
                loading={all.loading}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Pager({
  total,
  offset,
  count,
  onPage,
}: {
  total: number;
  offset: number;
  count: number;
  onPage: (offset: number) => void;
}) {
  if (total <= PAGE_SIZE && offset === 0) return null;
  const buttonClass =
    "rounded border border-edge-strong bg-surface-2 px-2.5 py-1 text-sm " +
    "hover:border-accent disabled:opacity-40 disabled:hover:border-edge-strong";
  return (
    <div className="flex items-center justify-between text-sm text-ink-dim">
      <span className="tabular-nums">
        Showing {offset + 1}–{offset + count} of {total}
      </span>
      <div className="flex gap-1.5">
        <button
          type="button"
          className={buttonClass}
          disabled={offset === 0}
          onClick={() => onPage(Math.max(0, offset - PAGE_SIZE))}
        >
          ← Prev
        </button>
        <button
          type="button"
          className={buttonClass}
          disabled={offset + count >= total}
          onClick={() => onPage(offset + PAGE_SIZE)}
        >
          Next →
        </button>
      </div>
    </div>
  );
}

function avgRecoveries(items: IncidentSummary[]): string {
  if (items.length === 0) return "—";
  const total = items.reduce((acc, item) => acc + item.recovery_attempts, 0);
  return (total / items.length).toFixed(1);
}

function FilterBar({
  filters,
  robotIds,
  searchText,
  onSearch,
  onChange,
  onClear,
}: {
  filters: Filters;
  robotIds: string[];
  searchText: string;
  onSearch: (text: string) => void;
  onChange: (filters: Filters) => void;
  onClear: () => void;
}) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  const active =
    searchText !== "" || Object.values(filters).some((v) => v !== "");
  const selectClass =
    "rounded border border-edge bg-surface-2 px-2 py-1.5 text-sm text-ink " +
    "focus:border-accent";
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="sr-only" htmlFor="filter-search">
        Search incidents
      </label>
      <input
        id="filter-search"
        type="search"
        placeholder="Search id, task, summary…"
        className={`${selectClass} min-w-[210px] flex-1`}
        value={searchText}
        onChange={(e) => onSearch(e.target.value)}
      />
      <label className="sr-only" htmlFor="filter-robot">
        Robot
      </label>
      <select
        id="filter-robot"
        className={selectClass}
        value={filters.robot_id}
        onChange={(e) => set({ robot_id: e.target.value })}
      >
        <option value="">All robots</option>
        {robotIds.map((id) => (
          <option key={id} value={id}>
            {id}
          </option>
        ))}
      </select>
      <label className="sr-only" htmlFor="filter-severity">
        Severity
      </label>
      <select
        id="filter-severity"
        className={selectClass}
        value={filters.severity}
        onChange={(e) => set({ severity: e.target.value })}
      >
        <option value="">All severities</option>
        {["info", "warning", "error", "critical"].map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
      <label className="sr-only" htmlFor="filter-category">
        Failure category
      </label>
      <select
        id="filter-category"
        className={selectClass}
        value={filters.failure_category}
        onChange={(e) => set({ failure_category: e.target.value })}
      >
        <option value="">All categories</option>
        {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <label className="sr-only" htmlFor="filter-outcome">
        Outcome
      </label>
      <select
        id="filter-outcome"
        className={selectClass}
        value={filters.outcome}
        onChange={(e) => set({ outcome: e.target.value })}
      >
        <option value="">All outcomes</option>
        {Object.entries(OUTCOME_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <label className="sr-only" htmlFor="filter-after">
        Started after
      </label>
      <input
        id="filter-after"
        type="date"
        className={selectClass}
        value={filters.start_after}
        onChange={(e) => set({ start_after: e.target.value })}
        aria-label="Started after date"
      />
      {active && (
        <button
          type="button"
          onClick={onClear}
          className="rounded border border-edge px-2 py-1.5 text-sm text-ink-dim hover:border-edge-strong hover:text-ink"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}

function IncidentTable({ items }: { items: IncidentSummary[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-edge bg-surface-1">
      <table className="w-full min-w-[760px] text-sm">
        <thead>
          <tr className="border-b border-edge text-left text-[11px] uppercase tracking-wider text-ink-faint">
            <th className="px-4 py-2.5 font-semibold">Incident</th>
            <th className="px-3 py-2.5 font-semibold">Robot</th>
            <th className="px-3 py-2.5 font-semibold">Severity</th>
            <th className="px-3 py-2.5 font-semibold">Outcome</th>
            <th className="px-3 py-2.5 font-semibold">Root cause</th>
            <th className="px-3 py-2.5 text-right font-semibold">Conf.</th>
            <th className="px-3 py-2.5 text-right font-semibold">Duration</th>
            <th className="px-4 py-2.5 text-right font-semibold">Start (UTC)</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className="border-b border-edge/60 last:border-b-0 hover:bg-surface-2/60"
            >
              <td className="px-4 py-3">
                <Link
                  href={`/incidents/${encodeURIComponent(item.id)}`}
                  className="font-medium text-ink hover:text-accent"
                >
                  {item.task_name}
                </Link>
                <p className="font-mono text-xs text-ink-faint">{item.id}</p>
              </td>
              <td className="px-3 py-3 font-mono text-xs">{item.robot_id}</td>
              <td className="px-3 py-3">
                <Badge className={SEVERITY_STYLES[item.severity]}>
                  {item.severity}
                </Badge>
              </td>
              <td className="px-3 py-3">
                <Badge className={OUTCOME_STYLES[item.outcome]}>
                  {OUTCOME_LABELS[item.outcome]}
                </Badge>
              </td>
              <td className="px-3 py-3">
                {item.failure_category ? (
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      aria-hidden
                      className="h-2 w-2 rounded-full"
                      style={{
                        background: CATEGORY_COLORS[item.failure_category],
                      }}
                    />
                    {CATEGORY_LABELS[item.failure_category]}
                  </span>
                ) : (
                  <span className="text-ink-faint">Not analyzed</span>
                )}
              </td>
              <td className="px-3 py-3 text-right tabular-nums">
                {confidencePct(item.confidence)}
              </td>
              <td className="px-3 py-3 text-right tabular-nums">
                {formatDuration(item.duration_s)}
              </td>
              <td className="px-4 py-3 text-right text-xs text-ink-dim">
                {formatDateTime(item.start_time)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FleetPanel({
  robots,
  loading,
}: {
  robots: Map<string, IncidentSummary[]>;
  loading: boolean;
}) {
  return (
    <div className="rounded-lg border border-edge bg-surface-1">
      <header className="border-b border-edge px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-dim">
          Robot fleet status
        </h2>
      </header>
      <ul className="divide-y divide-edge/60">
        {loading && (
          <li className="px-4 py-3 text-sm text-ink-faint">Loading…</li>
        )}
        {!loading && robots.size === 0 && (
          <li className="px-4 py-3 text-sm text-ink-faint">
            No robots reported yet
          </li>
        )}
        {[...robots.entries()].sort().map(([robotId, incidents]) => {
          const worst = incidents.some((i) => i.severity === "critical")
            ? "critical"
            : incidents.some((i) => i.severity === "error")
              ? "error"
              : "warning";
          const latest = incidents[0];
          return (
            <li
              key={robotId}
              className="flex items-center justify-between px-4 py-3"
            >
              <div>
                <p className="font-mono text-sm">{robotId}</p>
                <p className="text-xs text-ink-faint">
                  {latest ? latest.robot_model : ""}
                </p>
              </div>
              <div className="text-right">
                <Badge
                  className={
                    SEVERITY_STYLES[worst as keyof typeof SEVERITY_STYLES]
                  }
                >
                  {incidents.length} incident{incidents.length === 1 ? "" : "s"}
                </Badge>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function CategoryBreakdown({
  byCategory,
  total,
  loading,
}: {
  byCategory: Map<FailureCategory, number>;
  total: number;
  loading: boolean;
}) {
  const entries = [...byCategory.entries()].sort((a, b) => b[1] - a[1]);
  return (
    <div className="rounded-lg border border-edge bg-surface-1">
      <header className="border-b border-edge px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-dim">
          Failure categories
        </h2>
      </header>
      <div className="space-y-3 p-4">
        {loading && <p className="text-sm text-ink-faint">Loading…</p>}
        {!loading && entries.length === 0 && (
          <p className="text-sm text-ink-faint">No analyzed incidents</p>
        )}
        {entries.map(([category, count]) => (
          <div key={category}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span>{CATEGORY_LABELS[category]}</span>
              <span className="tabular-nums text-ink-dim">{count}</span>
            </div>
            <div
              className="h-1.5 overflow-hidden rounded-full bg-surface-2"
              role="img"
              aria-label={`${CATEGORY_LABELS[category]}: ${count} of ${total}`}
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: `${total ? (count / total) * 100 : 0}%`,
                  background: CATEGORY_COLORS[category],
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
