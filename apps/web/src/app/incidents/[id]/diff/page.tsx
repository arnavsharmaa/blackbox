"use client";

import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type {
  ChannelDiff,
  Incident,
  IncidentSummary,
  TelemetryChannel,
} from "@blackbox/schemas";
import { fetchDiff, fetchIncidentDetail, fetchIncidents } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { OUTCOME_LABELS, OUTCOME_STYLES } from "@/lib/format";
import { numericPoints, seriesByChannel, stringValueAt } from "@/lib/telemetry";
import {
  Badge,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
  StatCard,
} from "@/components/ui";

const CHART_MARGIN = { top: 6, right: 8, bottom: 4, left: 44 };
const CHART_HEIGHT = 120;
const BASELINE_COLOR = "#5d6875";

const CHANNEL_META: Record<
  TelemetryChannel,
  { label: string; color: string; unit: string }
> = {
  pos_x: { label: "Position X", color: "#60a5fa", unit: "m" },
  pos_y: { label: "Position Y", color: "#818cf8", unit: "m" },
  heading: { label: "Heading", color: "#22d3ee", unit: "rad" },
  linear_velocity: { label: "Linear velocity", color: "#34d399", unit: "m/s" },
  angular_velocity: {
    label: "Angular velocity",
    color: "#38bdf8",
    unit: "rad/s",
  },
  obstacle_distance: {
    label: "Obstacle distance",
    color: "#f59e0b",
    unit: "m",
  },
  goal_distance: { label: "Goal distance", color: "#a78bfa", unit: "m" },
  localization_confidence: {
    label: "Localization confidence",
    color: "#f472b6",
    unit: "",
  },
  planner_state: { label: "Planner state", color: "#e2e8f0", unit: "" },
  recovery_count: { label: "Recovery count", color: "#fb923c", unit: "" },
  battery_pct: { label: "Battery", color: "#4ade80", unit: "%" },
};

function formatEventType(eventType: string): string {
  return eventType.replaceAll("_", " ");
}

/** Same-task successful runs first, then same-task, then everything else. */
function rankCandidates(
  items: IncidentSummary[],
  incidentId: string,
  taskName: string | undefined,
): IncidentSummary[] {
  const score = (item: IncidentSummary): number => {
    if (item.task_name === taskName && item.outcome === "success") return 0;
    if (item.task_name === taskName) return 1;
    return 2;
  };
  return items
    .filter((item) => item.id !== incidentId)
    .sort((a, b) => score(a) - score(b) || a.id.localeCompare(b.id));
}

export default function DiffPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const detail = useApi(() => fetchIncidentDetail(id), [id]);
  const list = useApi(() => fetchIncidents({ limit: 200 }), []);
  const [baselineId, setBaselineId] = useState<string | null>(null);

  const candidates = useMemo(
    () =>
      rankCandidates(
        list.data?.items ?? [],
        id,
        detail.data?.incident.task_name,
      ),
    [list.data, detail.data, id],
  );

  // Default to the best-ranked baseline once both requests settle.
  const defaultBaseline = candidates[0];
  useEffect(() => {
    if (baselineId === null && defaultBaseline) {
      setBaselineId(defaultBaseline.id);
    }
  }, [defaultBaseline, baselineId]);

  if (detail.loading || list.loading)
    return <LoadingState label="Loading runs…" />;
  if (detail.error)
    return <ErrorState error={detail.error} onRetry={detail.refetch} />;
  if (list.error)
    return <ErrorState error={list.error} onRetry={list.refetch} />;
  const incident = detail.data?.incident;
  if (!incident) return null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Incident comparison</h1>
          <p className="mt-1 text-sm text-ink-dim">
            <Link
              href={`/incidents/${encodeURIComponent(id)}`}
              className="font-mono text-accent hover:underline"
            >
              {incident.id}
            </Link>{" "}
            against a baseline run, aligned on seconds from each run&apos;s
            start.
          </p>
        </div>
        {candidates.length > 0 && (
          <label className="flex items-center gap-2 text-sm text-ink-dim">
            Baseline
            <select
              value={baselineId ?? ""}
              onChange={(event) => setBaselineId(event.target.value)}
              className="rounded border border-edge-strong bg-surface-2 px-2 py-1.5 text-sm text-ink"
            >
              {candidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.id} — {candidate.task_name} (
                  {OUTCOME_LABELS[candidate.outcome]})
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {candidates.length === 0 ? (
        <EmptyState
          title="No other runs to compare against"
          hint="Record or upload a successful run of the same task to use as a baseline."
        />
      ) : (
        baselineId && <DiffBody incident={incident} baselineId={baselineId} />
      )}
    </div>
  );
}

function DiffBody({
  incident,
  baselineId,
}: {
  incident: Incident;
  baselineId: string;
}) {
  const diff = useApi(
    () => fetchDiff(incident.id, baselineId),
    [incident.id, baselineId],
  );
  const baselineDetail = useApi(
    () => fetchIncidentDetail(baselineId),
    [baselineId],
  );

  if (diff.loading || baselineDetail.loading)
    return <LoadingState label="Comparing runs…" />;
  if (diff.error) return <ErrorState error={diff.error} onRetry={diff.refetch} />;
  if (baselineDetail.error)
    return (
      <ErrorState
        error={baselineDetail.error}
        onRetry={baselineDetail.refetch}
      />
    );
  const data = diff.data;
  const baseline = baselineDetail.data?.incident;
  if (!data || !baseline) return null;

  const divergingCount = data.channels.filter(
    (channel) => channel.first_divergence_t !== null,
  ).length;
  const firstChannel = data.first_divergence_channel;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="First divergence"
          value={
            data.first_divergence_t !== null
              ? `${data.first_divergence_t.toFixed(1)} s`
              : "none"
          }
          sub={firstChannel ? CHANNEL_META[firstChannel].label : "runs match"}
          accent={data.first_divergence_t !== null}
        />
        <StatCard
          label="Diverging channels"
          value={`${divergingCount} / ${data.channels.length}`}
        />
        <StatCard
          label="Failure-only event types"
          value={data.event_types_only_in_incident.length}
        />
        <div className="rounded-lg border border-edge bg-surface-1 px-4 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
            Outcomes
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-sm">
            <Badge className={OUTCOME_STYLES[data.incident.outcome]}>
              {OUTCOME_LABELS[data.incident.outcome]}
            </Badge>
            <span className="text-ink-faint">vs</span>
            <Badge className={OUTCOME_STYLES[data.baseline.outcome]}>
              {OUTCOME_LABELS[data.baseline.outcome]}
            </Badge>
          </div>
        </div>
      </div>

      {data.first_divergence_t !== null && firstChannel && (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-200">
          The runs first diverge at{" "}
          <span className="font-mono tabular-nums">
            {data.first_divergence_t.toFixed(1)} s
          </span>{" "}
          in <strong>{CHANNEL_META[firstChannel].label}</strong>.{" "}
          <Link
            href={`/incidents/${encodeURIComponent(incident.id)}?t=${data.first_divergence_t}`}
            className="text-accent hover:underline"
          >
            Open the replay at that moment →
          </Link>
        </p>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Panel title="Telemetry — incident vs baseline (dashed)">
          <div className="divide-y divide-edge/50">
            {data.channels.map((channel) => (
              <DiffChart
                key={channel.channel}
                diff={channel}
                incident={incident}
                baseline={baseline}
              />
            ))}
          </div>
        </Panel>

        <Panel title="Events by type">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-edge text-left text-[10px] uppercase tracking-wider text-ink-faint">
                <th className="py-1.5 pr-2 font-semibold">Event type</th>
                <th className="py-1.5 pr-2 text-right font-semibold">
                  Incident
                </th>
                <th className="py-1.5 text-right font-semibold">Baseline</th>
              </tr>
            </thead>
            <tbody>
              {data.events.map((entry) => {
                const failureOnly =
                  entry.baseline_count === 0 && entry.incident_count > 0;
                return (
                  <tr
                    key={entry.event_type}
                    className="border-b border-edge/50 last:border-b-0"
                  >
                    <td
                      className={`py-1.5 pr-2 ${failureOnly ? "text-amber-300" : ""}`}
                    >
                      {formatEventType(entry.event_type)}
                      {failureOnly && (
                        <span className="ml-1.5 text-[10px] uppercase tracking-wider text-amber-500/80">
                          only here
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 pr-2 text-right font-mono tabular-nums">
                      {entry.incident_count}
                    </td>
                    <td className="py-1.5 text-right font-mono tabular-nums text-ink-dim">
                      {entry.baseline_count}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}

function DiffChart({
  diff,
  incident,
  baseline,
}: {
  diff: ChannelDiff;
  incident: Incident;
  baseline: Incident;
}) {
  const meta = CHANNEL_META[diff.channel];
  const incidentChannels = useMemo(
    () => seriesByChannel(incident),
    [incident],
  );
  const baselineChannels = useMemo(
    () => seriesByChannel(baseline),
    [baseline],
  );

  // String channels (planner_state) get a textual row instead of a chart.
  if (diff.delta_threshold === null) {
    const t = diff.first_divergence_t;
    return (
      <div className="px-2 py-2.5">
        <ChartHeader diff={diff} />
        <p className="mt-1 px-2 text-sm text-ink-dim">
          {t !== null ? (
            <>
              At{" "}
              <span className="font-mono tabular-nums">{t.toFixed(1)} s</span>{" "}
              the incident enters{" "}
              <span className="font-mono">
                {stringValueAt(incidentChannels[diff.channel], t) ?? "?"}
              </span>{" "}
              while the baseline is{" "}
              <span className="font-mono">
                {stringValueAt(baselineChannels[diff.channel], t) ?? "?"}
              </span>
              .
            </>
          ) : (
            "States match for the whole overlap window."
          )}
        </p>
      </div>
    );
  }

  const incidentPoints = numericPoints(incidentChannels[diff.channel]);
  const baselinePoints = numericPoints(baselineChannels[diff.channel]);
  const duration = Math.max(
    incidentPoints.at(-1)?.t ?? 0,
    baselinePoints.at(-1)?.t ?? 0,
  );

  return (
    <div className="px-2 py-1.5">
      <ChartHeader diff={diff} />
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <LineChart margin={CHART_MARGIN}>
          <XAxis
            dataKey="t"
            type="number"
            domain={[0, duration]}
            hide
            allowDataOverflow
          />
          <YAxis
            width={CHART_MARGIN.left - 4}
            tick={{ fill: "#5d6875", fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: "#232b36" }}
            domain={["auto", "auto"]}
          />
          {diff.first_divergence_t !== null && (
            <ReferenceLine
              x={diff.first_divergence_t}
              stroke="#f87171"
              strokeDasharray="4 3"
              strokeOpacity={0.8}
            />
          )}
          <Line
            data={baselinePoints}
            type="linear"
            dataKey="value"
            stroke={BASELINE_COLOR}
            strokeWidth={1.5}
            strokeDasharray="5 4"
            dot={false}
            isAnimationActive={false}
          />
          <Line
            data={incidentPoints}
            type="linear"
            dataKey="value"
            stroke={meta.color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartHeader({ diff }: { diff: ChannelDiff }) {
  const meta = CHANNEL_META[diff.channel];
  return (
    <div className="flex items-baseline justify-between px-2">
      <span className="text-xs font-medium text-ink-dim">
        <span
          aria-hidden
          className="mr-1.5 inline-block h-2 w-2 rounded-full align-baseline"
          style={{ background: meta.color }}
        />
        {meta.label}
      </span>
      <span className="text-xs text-ink-faint">
        {diff.first_divergence_t !== null ? (
          <>
            diverges at{" "}
            <span className="font-mono tabular-nums text-amber-300">
              {diff.first_divergence_t.toFixed(1)} s
            </span>
            {diff.max_abs_delta !== null && (
              <>
                {" · max Δ "}
                <span className="font-mono tabular-nums">
                  {diff.max_abs_delta.toFixed(2)}
                  {meta.unit && ` ${meta.unit}`}
                </span>
              </>
            )}
          </>
        ) : (
          "no divergence"
        )}
      </span>
    </div>
  );
}
