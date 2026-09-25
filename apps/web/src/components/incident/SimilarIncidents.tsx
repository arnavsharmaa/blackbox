"use client";

import Link from "next/link";
import { fetchSimilar } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatDateTime } from "@/lib/format";

/**
 * "This happened before": past incidents sharing this one's failure
 * signature (same task, same diagnosed category). Renders nothing when
 * the incident is a first occurrence, so one-offs stay uncluttered.
 */
export function SimilarIncidents({ incidentId }: { incidentId: string }) {
  const similar = useApi(() => fetchSimilar(incidentId), [incidentId]);
  const items = Array.isArray(similar.data) ? similar.data : [];
  if (similar.loading || similar.error || items.length === 0) return null;

  return (
    <div className="rounded-lg border border-amber-500/30 bg-surface-1">
      <header className="border-b border-amber-500/20 px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-amber-300">
          This happened before
        </h2>
      </header>
      <ul className="divide-y divide-edge/60">
        {items.map((item) => (
          <li key={item.id} className="px-4 py-2.5">
            <Link
              href={`/incidents/${encodeURIComponent(item.id)}`}
              className="font-mono text-sm text-ink hover:text-accent"
            >
              {item.id}
            </Link>
            <p className="mt-0.5 text-xs text-ink-faint">
              <span className="font-mono">{item.robot_id}</span> ·{" "}
              {formatDateTime(item.start_time)}
            </p>
          </li>
        ))}
      </ul>
      <p className="border-t border-edge/60 px-4 py-2 text-xs text-ink-faint">
        Same task failing the same way — see{" "}
        <Link href="/analytics" className="text-accent hover:underline">
          recurring failures
        </Link>{" "}
        for the fleet-wide view.
      </p>
    </div>
  );
}
