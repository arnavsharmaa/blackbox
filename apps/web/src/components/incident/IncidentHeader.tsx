"use client";

import Link from "next/link";
import type { AnalysisResult, Incident } from "@blackbox/schemas";
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
import { Badge } from "@/components/ui";

export function IncidentHeader({
  incident,
  analysis,
}: {
  incident: Incident;
  analysis: AnalysisResult | null;
}) {
  return (
    <div className="rounded-lg border border-edge bg-surface-1 px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-lg font-semibold">{incident.task_name}</h1>
            <Badge className={SEVERITY_STYLES[incident.severity]}>
              {incident.severity}
            </Badge>
            <Badge className={OUTCOME_STYLES[incident.outcome]}>
              {OUTCOME_LABELS[incident.outcome]}
            </Badge>
          </div>
          <p className="mt-1 font-mono text-xs text-ink-faint">{incident.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={`/incidents/${encodeURIComponent(incident.id)}/report`}
            className="rounded border border-edge-strong bg-surface-2 px-3 py-1.5 text-sm hover:border-accent"
          >
            Report
          </Link>
          <Link
            href={`/incidents/${encodeURIComponent(incident.id)}/issue`}
            className="rounded border border-edge-strong bg-surface-2 px-3 py-1.5 text-sm hover:border-accent"
          >
            GitHub issue
          </Link>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3 lg:grid-cols-5">
        <Meta label="Robot">
          <span className="font-mono">{incident.robot_id}</span>{" "}
          <span className="text-ink-faint">({incident.robot_model})</span>
        </Meta>
        <Meta label="Started (UTC)">{formatDateTime(incident.start_time)}</Meta>
        <Meta label="Duration">
          {formatDuration(
            (new Date(incident.end_time).getTime() -
              new Date(incident.start_time).getTime()) /
              1000,
          )}
        </Meta>
        <Meta label="Software">
          <span className="font-mono text-xs">{incident.software_version}</span>
        </Meta>
        <Meta label="Facility">{incident.facility}</Meta>
        <Meta label="Root cause">
          {analysis ? (
            <span className="inline-flex items-center gap-1.5">
              <span
                aria-hidden
                className="h-2 w-2 rounded-full"
                style={{
                  background: CATEGORY_COLORS[analysis.failure_category],
                }}
              />
              {CATEGORY_LABELS[analysis.failure_category]}
            </span>
          ) : (
            <span className="text-ink-faint">Not analyzed</span>
          )}
        </Meta>
        <Meta label="Confidence">
          <span className="tabular-nums">
            {analysis ? confidencePct(analysis.confidence) : "—"}
          </span>
        </Meta>
        <Meta label="Map version">
          <span className="font-mono text-xs">{incident.map_version}</span>
        </Meta>
        <Meta label="Environment">{incident.environment}</Meta>
        <Meta label="Events">{incident.events.length}</Meta>
      </dl>
    </div>
  );
}

function Meta({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
        {label}
      </dt>
      <dd className="mt-0.5 truncate" title={typeof children === "string" ? children : undefined}>
        {children}
      </dd>
    </div>
  );
}
