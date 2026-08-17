"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { AnalyticsResponse, FailureCategory } from "@blackbox/schemas";
import { fetchAnalytics } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import {
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  OUTCOME_LABELS,
  OUTCOME_STYLES,
} from "@/lib/format";
import {
  Badge,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
  StatCard,
} from "@/components/ui";

const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS) as FailureCategory[];

export default function AnalyticsPage() {
  const analytics = useApi(fetchAnalytics, []);

  if (analytics.loading) return <LoadingState label="Crunching fleet data…" />;
  if (analytics.error)
    return <ErrorState error={analytics.error} onRetry={analytics.refetch} />;
  const data = analytics.data;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Fleet analytics</h1>
        <p className="mt-1 text-sm text-ink-dim">
          Cross-incident trends: what fails, where, on which robots and
          software versions.
        </p>
      </div>

      {data.total_incidents === 0 ? (
        <EmptyState
          title="No incidents recorded yet"
          hint="Seed the demo data with `make seed`, or upload an incident."
        />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Total incidents" value={data.total_incidents} />
            <StatCard
              label="Critical incidents"
              value={data.critical_incidents}
              accent={data.critical_incidents > 0}
            />
            <StatCard
              label="Recovery attempts"
              value={data.total_recovery_attempts}
              sub="fleet-wide"
            />
            <StatCard
              label="Robots with incidents"
              value={data.by_robot.length}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <DailyTrend data={data} />
            <Panel title="Blockage hotspots">
              {data.blockage_hotspots.length === 0 ? (
                <p className="text-sm text-ink-faint">
                  No recurring obstacle locations detected.
                </p>
              ) : (
                <ul className="space-y-2">
                  {data.blockage_hotspots.map((spot) => (
                    <li
                      key={`${spot.facility}-${spot.x}-${spot.y}`}
                      className="flex items-start justify-between gap-3 rounded border border-edge bg-surface-2/50 px-3 py-2"
                    >
                      <div>
                        <p className="text-sm">
                          {spot.facility}{" "}
                          <span className="font-mono text-xs text-ink-dim">
                            ({spot.x.toFixed(1)}, {spot.y.toFixed(1)}) m
                          </span>
                        </p>
                        <p className="mt-0.5 text-xs text-ink-faint">
                          {spot.incident_ids.map((id, index) => (
                            <span key={id}>
                              {index > 0 && ", "}
                              <Link
                                href={`/incidents/${encodeURIComponent(id)}`}
                                className="font-mono hover:text-accent"
                              >
                                {id}
                              </Link>
                            </span>
                          ))}
                        </p>
                      </div>
                      <Badge className="border-amber-500/30 bg-amber-500/10 text-amber-300">
                        ×{spot.count}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="By robot">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-edge text-left text-[10px] uppercase tracking-wider text-ink-faint">
                    <th className="py-1.5 pr-3 font-semibold">Robot</th>
                    <th className="py-1.5 pr-3 text-right font-semibold">
                      Incidents
                    </th>
                    <th className="py-1.5 pr-3 text-right font-semibold">
                      Critical
                    </th>
                    <th className="py-1.5 pr-3 text-right font-semibold">
                      Recoveries
                    </th>
                    <th className="py-1.5 font-semibold">Top cause</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_robot.map((robot) => (
                    <tr
                      key={robot.robot_id}
                      className="border-b border-edge/50 last:border-b-0"
                    >
                      <td className="py-2 pr-3">
                        <span className="font-mono">{robot.robot_id}</span>
                        <span className="ml-2 text-xs text-ink-faint">
                          {robot.robot_model}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {robot.incidents}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {robot.critical}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {robot.recovery_attempts}
                      </td>
                      <td className="py-2">
                        {robot.top_category ? (
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span
                              aria-hidden
                              className="h-2 w-2 rounded-full"
                              style={{
                                background:
                                  CATEGORY_COLORS[robot.top_category],
                              }}
                            />
                            {CATEGORY_LABELS[robot.top_category]}
                          </span>
                        ) : (
                          <span className="text-xs text-ink-faint">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>

            <Panel title="By software version">
              {data.by_software_version.map((version) => (
                <div
                  key={version.software_version}
                  className="border-b border-edge/50 py-2.5 first:pt-0 last:border-b-0 last:pb-0"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm">
                      {version.software_version}
                    </span>
                    <span className="text-sm tabular-nums text-ink-dim">
                      {version.incidents} incident
                      {version.incidents === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {version.categories.map((entry) => (
                      <Badge
                        key={entry.category}
                        className="border-edge-strong bg-surface-2 text-ink-dim"
                        title={CATEGORY_LABELS[entry.category]}
                      >
                        <span
                          aria-hidden
                          className="h-1.5 w-1.5 rounded-full"
                          style={{
                            background: CATEGORY_COLORS[entry.category],
                          }}
                        />
                        {CATEGORY_LABELS[entry.category]} ×{entry.count}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </Panel>
          </div>

          <Panel title="Diagnosis calibration">
            {data.calibration.length === 0 ? (
              <p className="text-sm text-ink-faint">
                No engineer verdicts yet. Confirm or correct a diagnosis on an
                incident page and measured precision per category will appear
                here.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-edge text-left text-[10px] uppercase tracking-wider text-ink-faint">
                    <th className="py-1.5 pr-3 font-semibold">
                      Diagnosed category
                    </th>
                    <th className="py-1.5 pr-3 text-right font-semibold">
                      Reviewed
                    </th>
                    <th className="py-1.5 pr-3 text-right font-semibold">
                      Confirmed
                    </th>
                    <th className="py-1.5 pr-3 text-right font-semibold">
                      Precision
                    </th>
                    <th className="py-1.5 font-semibold">Corrections went to</th>
                  </tr>
                </thead>
                <tbody>
                  {data.calibration.map((row) => (
                    <tr
                      key={row.category}
                      className="border-b border-edge/50 last:border-b-0"
                    >
                      <td className="py-2 pr-3">
                        <span className="inline-flex items-center gap-1.5">
                          <span
                            aria-hidden
                            className="h-2 w-2 rounded-full"
                            style={{
                              background: CATEGORY_COLORS[row.category],
                            }}
                          />
                          {CATEGORY_LABELS[row.category]}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {row.reviewed}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {row.confirmed}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono tabular-nums">
                        {Math.round(row.precision * 100)}%
                      </td>
                      <td className="py-2 text-xs text-ink-dim">
                        {row.corrected_to.length === 0
                          ? "—"
                          : row.corrected_to
                              .map(
                                (entry) =>
                                  `${CATEGORY_LABELS[entry.category]} ×${entry.count}`,
                              )
                              .join(", ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          <Panel title="Outcomes">
            <div className="flex flex-wrap gap-2">
              {data.outcomes.map((entry) => (
                <Badge
                  key={entry.outcome}
                  className={OUTCOME_STYLES[entry.outcome]}
                >
                  {OUTCOME_LABELS[entry.outcome]} ×{entry.count}
                </Badge>
              ))}
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

function DailyTrend({ data }: { data: AnalyticsResponse }) {
  // Pivot [{date, category, count}] into one row per date for stacked bars.
  const rows = useMemo(() => {
    const byDate = new Map<string, Record<string, number | string>>();
    for (const entry of data.daily) {
      const row = byDate.get(entry.date) ?? { date: entry.date.slice(5) };
      row[entry.category] = entry.count;
      byDate.set(entry.date, row);
    }
    return [...byDate.values()];
  }, [data.daily]);

  const present = useMemo(
    () =>
      ALL_CATEGORIES.filter((category) =>
        data.daily.some((entry) => entry.category === category),
      ),
    [data.daily],
  );

  return (
    <Panel title="Failures by day">
      {rows.length === 0 ? (
        <p className="text-sm text-ink-faint">No analyzed incidents.</p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
              <XAxis
                dataKey="date"
                tick={{ fill: "#5d6875", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#232b36" }}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: "#5d6875", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#232b36" }}
              />
              {present.map((category) => (
                <Bar
                  key={category}
                  dataKey={category}
                  stackId="failures"
                  fill={CATEGORY_COLORS[category]}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-faint">
            {present.map((category) => (
              <span key={category} className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden
                  className="inline-block h-2 w-2 rounded-sm"
                  style={{ background: CATEGORY_COLORS[category] }}
                />
                {CATEGORY_LABELS[category]}
              </span>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}
