"use client";

import type { Incident } from "@blackbox/schemas";
import { useReplayStore } from "@/store/replay";
import { eventOffsetSeconds } from "@/lib/telemetry";
import { SEVERITY_STYLES } from "@/lib/format";
import { Badge } from "@/components/ui";

export function EventInspector({ incident }: { incident: Incident }) {
  const selectedEvent = useReplayStore((s) => s.selectedEvent);
  const event =
    selectedEvent !== null ? incident.events[selectedEvent] : undefined;

  return (
    <div className="rounded-lg border border-edge bg-surface-1">
      <header className="border-b border-edge px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-dim">
          Event inspector
        </h2>
      </header>
      {!event ? (
        <p className="px-4 py-6 text-sm text-ink-faint">
          Select an event on the timeline to inspect its payload.
        </p>
      ) : (
        <div className="space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={SEVERITY_STYLES[event.severity]}>
              {event.severity}
            </Badge>
            <Badge className="border-edge-strong bg-surface-2 text-ink-dim">
              {event.event_type}
            </Badge>
            <Badge className="border-edge-strong bg-surface-2 text-ink-dim">
              {event.subsystem}
            </Badge>
            <span className="ml-auto font-mono text-xs tabular-nums text-accent">
              t={eventOffsetSeconds(incident, event).toFixed(1)}s
            </span>
          </div>
          <p className="text-sm">{event.message}</p>
          {event.correlation_id && (
            <p className="text-xs text-ink-faint">
              correlation: <span className="font-mono">{event.correlation_id}</span>
            </p>
          )}
          <pre className="panel-scroll max-h-56 overflow-auto rounded border border-edge bg-surface-0 p-3 font-mono text-xs leading-relaxed text-sky-200">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
          {event.evidence_tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {event.evidence_tags.map((tag) => (
                <Badge
                  key={tag}
                  className="border-amber-500/30 bg-amber-500/10 text-amber-300"
                >
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
