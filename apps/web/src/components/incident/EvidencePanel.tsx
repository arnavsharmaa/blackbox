"use client";

import type { AnalysisResult } from "@blackbox/schemas";
import { useReplayStore } from "@/store/replay";
import { Badge } from "@/components/ui";

export function EvidencePanel({ analysis }: { analysis: AnalysisResult }) {
  const time = useReplayStore((s) => s.time);

  return (
    <div className="rounded-lg border border-edge bg-surface-1">
      <header className="flex items-center justify-between border-b border-edge px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-dim">
          Evidence
        </h2>
        <Badge className="border-edge-strong bg-surface-2 text-ink-dim">
          {analysis.evidence.length} items
        </Badge>
      </header>
      {analysis.evidence.length === 0 ? (
        <p className="px-4 py-6 text-sm text-ink-faint">
          No evidence items were produced for this diagnosis.
        </p>
      ) : (
        <ul className="divide-y divide-edge/50 panel-scroll max-h-[380px] overflow-y-auto">
          {analysis.evidence.map((item) => {
            const inWindow =
              time >= item.t && time <= (item.t_end ?? item.t + 0.5);
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => useReplayStore.getState().seek(item.t)}
                  className={`w-full px-4 py-2.5 text-left hover:bg-surface-2/70 ${
                    inWindow ? "bg-amber-500/10" : ""
                  }`}
                  aria-label={`Jump to ${item.t.toFixed(1)} seconds: ${item.summary}`}
                >
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 shrink-0 rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-accent">
                      t={item.t.toFixed(1)}s
                      {item.t_end !== null && item.t_end !== undefined
                        ? `–${item.t_end.toFixed(1)}s`
                        : ""}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm leading-snug">{item.summary}</p>
                      {item.detail && (
                        <p className="mt-0.5 text-xs leading-snug text-ink-faint">
                          {item.detail}
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
