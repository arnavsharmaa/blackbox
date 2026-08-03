"use client";

import { use } from "react";
import Link from "next/link";
import { fetchReport } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { downloadFile } from "@/lib/export";
import {
  SEVERITY_STYLES,
  confidencePct,
  formatDateTime,
} from "@/lib/format";
import type { Severity } from "@blackbox/schemas";
import { Badge, ErrorState, LoadingState, Panel } from "@/components/ui";
import { CopyButton } from "@/components/CopyButton";

const META_ROWS: [string, string][] = [
  ["Robot", "robot_id"],
  ["Model", "robot_model"],
  ["Facility", "facility"],
  ["Environment", "environment"],
  ["Task", "task_name"],
  ["Goal", "task_goal"],
  ["Outcome", "outcome"],
  ["Severity", "severity"],
  ["Software version", "software_version"],
  ["Map version", "map_version"],
  ["Duration (s)", "duration_s"],
  ["Events recorded", "event_count"],
];

export default function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const report = useApi(() => fetchReport(id), [id]);

  if (report.loading) return <LoadingState label="Building report…" />;
  if (report.error)
    return <ErrorState error={report.error} onRetry={report.refetch} />;
  const data = report.data;
  if (!data) return null;

  const handleDownloadJson = () => {
    const clean = { ...data } as Record<string, unknown>;
    delete clean.markdown;
    downloadFile(
      `${id}-report.json`,
      JSON.stringify(clean, null, 2),
      "application/json",
    );
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4 print:max-w-none">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <nav className="text-sm text-ink-dim">
          <Link href="/" className="hover:text-ink">
            Incidents
          </Link>
          {" / "}
          <Link
            href={`/incidents/${encodeURIComponent(id)}`}
            className="hover:text-ink"
          >
            {id}
          </Link>
          {" / report"}
        </nav>
        <div className="flex gap-2">
          <CopyButton text={data.markdown} label="Copy Markdown" />
          <button
            type="button"
            onClick={handleDownloadJson}
            className="rounded border border-edge-strong bg-surface-2 px-3 py-1.5 text-sm hover:border-accent"
          >
            Download JSON
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded border border-edge-strong bg-surface-2 px-3 py-1.5 text-sm hover:border-accent"
          >
            Print view
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-edge bg-surface-1 px-6 py-5 print:border-0">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
          BlackBox incident report
        </p>
        <h1 className="mt-1 font-mono text-xl font-semibold">
          {String(data.incident.id ?? id)}
        </h1>
        <p className="mt-3 text-sm leading-relaxed">
          {String(data.incident.summary ?? "")}
        </p>
        {data.root_cause && (
          <div className="mt-4 rounded border border-amber-500/30 bg-amber-500/5 p-4">
            <p className="text-sm">
              <span className="font-semibold text-accent">
                Root cause: {data.root_cause.category_label}
              </span>{" "}
              <span className="tabular-nums text-ink-dim">
                (confidence {confidencePct(data.root_cause.confidence)})
              </span>
            </p>
            <p className="mt-2 text-sm leading-relaxed text-ink-dim">
              {data.root_cause.explanation}
            </p>
            <p className="mt-2 text-xs text-ink-faint">
              Rules triggered: {data.root_cause.rules_triggered.join(", ")} ·
              engine v{data.root_cause.engine_version}
            </p>
          </div>
        )}
        {data.ai_explanation && (
          <div className="mt-3 rounded border border-violet-500/30 bg-violet-500/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-violet-300">
              AI-generated explanation
            </p>
            <p className="mt-1 text-sm text-ink-dim">{data.ai_explanation}</p>
          </div>
        )}
      </div>

      <Panel title="Incident metadata">
        <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm md:grid-cols-3">
          {META_ROWS.map(([label, key]) => (
            <div key={key}>
              <dt className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
                {label}
              </dt>
              <dd className="mt-0.5 break-words">
                {String(data.incident[key] ?? "—")}
              </dd>
            </div>
          ))}
          <div>
            <dt className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
              Window (UTC)
            </dt>
            <dd className="mt-0.5 text-xs">
              {formatDateTime(String(data.incident.start_time))} →{" "}
              {formatDateTime(String(data.incident.end_time))}
            </dd>
          </div>
        </dl>
      </Panel>

      {data.evidence.length > 0 && (
        <Panel title="Evidence">
          <ul className="space-y-2 text-sm">
            {data.evidence.map((item) => (
              <li key={item.id} className="flex gap-3">
                <span className="shrink-0 font-mono text-xs tabular-nums text-accent">
                  t={item.t.toFixed(1)}s
                  {item.t_end != null ? `–${item.t_end.toFixed(1)}s` : ""}
                </span>
                <span>{item.summary}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {data.recommended_actions.length > 0 && (
        <Panel title="Recommended actions">
          <ol className="list-decimal space-y-1.5 pl-5 text-sm">
            {data.recommended_actions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ol>
        </Panel>
      )}

      <Panel title="Key timeline">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-edge text-left text-[10px] uppercase tracking-wider text-ink-faint">
                <th className="py-1.5 pr-3 font-semibold">t</th>
                <th className="py-1.5 pr-3 font-semibold">Type</th>
                <th className="py-1.5 pr-3 font-semibold">Subsystem</th>
                <th className="py-1.5 pr-3 font-semibold">Severity</th>
                <th className="py-1.5 font-semibold">Message</th>
              </tr>
            </thead>
            <tbody>
              {data.timeline.map((event, i) => (
                <tr
                  key={`${event.t}-${i}`}
                  className="border-b border-edge/50 last:border-b-0"
                >
                  <td className="py-1.5 pr-3 font-mono text-xs tabular-nums text-accent">
                    {event.t.toFixed(1)}s
                  </td>
                  <td className="py-1.5 pr-3 font-mono text-xs">
                    {event.event_type}
                  </td>
                  <td className="py-1.5 pr-3 text-xs">{event.subsystem}</td>
                  <td className="py-1.5 pr-3">
                    <Badge
                      className={SEVERITY_STYLES[event.severity as Severity]}
                    >
                      {event.severity}
                    </Badge>
                  </td>
                  <td className="py-1.5 text-xs">{event.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Telemetry summary">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-edge text-left text-[10px] uppercase tracking-wider text-ink-faint">
                <th className="py-1.5 pr-3 font-semibold">Channel</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Min</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Max</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Last</th>
                <th className="py-1.5 text-right font-semibold">Samples</th>
              </tr>
            </thead>
            <tbody>
              {data.telemetry_summary.map((row) => (
                <tr
                  key={row.channel}
                  className="border-b border-edge/50 last:border-b-0"
                >
                  <td className="py-1.5 pr-3 font-mono text-xs">
                    {row.channel}
                    {row.unit && (
                      <span className="text-ink-faint"> ({row.unit})</span>
                    )}
                  </td>
                  <td className="py-1.5 pr-3 text-right font-mono text-xs tabular-nums">
                    {row.min}
                  </td>
                  <td className="py-1.5 pr-3 text-right font-mono text-xs tabular-nums">
                    {row.max}
                  </td>
                  <td className="py-1.5 pr-3 text-right font-mono text-xs tabular-nums">
                    {row.last}
                  </td>
                  <td className="py-1.5 text-right font-mono text-xs tabular-nums">
                    {row.samples}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Reproduction notes">
        <p className="text-sm leading-relaxed">{data.reproduction.notes}</p>
        <p className="mt-2 text-sm print:hidden">
          <Link
            href={`/incidents/${encodeURIComponent(id)}`}
            className="text-accent hover:underline"
          >
            Open the deterministic replay →
          </Link>
        </p>
      </Panel>
    </div>
  );
}
