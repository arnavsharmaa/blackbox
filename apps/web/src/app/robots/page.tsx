"use client";

import Link from "next/link";
import { fetchAnalytics } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { CATEGORY_COLORS, CATEGORY_LABELS } from "@/lib/format";
import {
  Badge,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
} from "@/components/ui";

/**
 * Fleet roster: one row per robot with its incident record, worst
 * severity, recovery count, and dominant failure mode — each linking to
 * the overview pre-filtered to that robot.
 */
export default function RobotsPage() {
  const analytics = useApi(() => fetchAnalytics(), []);

  if (analytics.loading) return <LoadingState label="Loading the fleet…" />;
  if (analytics.error)
    return <ErrorState error={analytics.error} onRetry={analytics.refetch} />;
  const robots = analytics.data?.by_robot ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Robots</h1>
        <p className="mt-1 text-sm text-ink-dim">
          Every robot with recorded incidents. Click through for its
          incident history.
        </p>
      </div>

      {robots.length === 0 ? (
        <EmptyState
          title="No robots reported yet"
          hint="Seed the demo data with `make seed`, or upload an incident."
        />
      ) : (
        <Panel>
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
                <th className="py-1.5 font-semibold">Top failure mode</th>
              </tr>
            </thead>
            <tbody>
              {robots.map((robot) => (
                <tr
                  key={robot.robot_id}
                  className="border-b border-edge/50 last:border-b-0 hover:bg-surface-2/60"
                >
                  <td className="py-2.5 pr-3">
                    <Link
                      href={`/?robot_id=${encodeURIComponent(robot.robot_id)}`}
                      className="font-mono text-ink hover:text-accent"
                    >
                      {robot.robot_id}
                    </Link>
                    <p className="text-xs text-ink-faint">
                      {robot.robot_model}
                    </p>
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">
                    {robot.incidents}
                  </td>
                  <td className="py-2.5 pr-3 text-right">
                    {robot.critical > 0 ? (
                      <Badge className="border-red-500/40 bg-red-950/30 text-red-300">
                        {robot.critical}
                      </Badge>
                    ) : (
                      <span className="tabular-nums text-ink-faint">0</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">
                    {robot.recovery_attempts}
                  </td>
                  <td className="py-2.5">
                    {robot.top_category ? (
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          aria-hidden
                          className="h-2 w-2 rounded-full"
                          style={{
                            background: CATEGORY_COLORS[robot.top_category],
                          }}
                        />
                        {CATEGORY_LABELS[robot.top_category]}
                      </span>
                    ) : (
                      <span className="text-ink-faint">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}
