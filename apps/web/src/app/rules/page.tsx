"use client";

import Link from "next/link";
import type { RuleInfo } from "@blackbox/schemas";
import { fetchRules } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { CATEGORY_COLORS, CATEGORY_LABELS } from "@/lib/format";
import { Badge, ErrorState, LoadingState, Panel } from "@/components/ui";

export default function RulesPage() {
  const rules = useApi(fetchRules, []);

  if (rules.loading) return <LoadingState label="Loading rules…" />;
  if (rules.error)
    return <ErrorState error={rules.error} onRetry={rules.refetch} />;
  const data = rules.data;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Analysis rules</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-dim">
          Every root cause BlackBox reports comes from one of these
          deterministic rules — never from an LLM. Engine{" "}
          <span className="font-mono text-xs">{data.engine_version}</span>: a
          rule must score at least{" "}
          {Math.round(data.diagnosis_threshold * 100)}% to claim a diagnosis,
          and reported confidence is capped at{" "}
          {Math.round(data.confidence_ceiling * 100)}% because rules are
          heuristics. Deployments can add rules without forking via{" "}
          <span className="font-mono text-xs">BLACKBOX_EXTRA_RULES</span>.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {data.rules.map((rule) => (
          <RuleCard key={rule.rule_id} rule={rule} />
        ))}
      </div>
    </div>
  );
}

function RuleCard({ rule }: { rule: RuleInfo }) {
  return (
    <Panel
      title={
        <span className="inline-flex items-center gap-2">
          {rule.category && (
            <span
              aria-hidden
              className="h-2 w-2 rounded-full"
              style={{ background: CATEGORY_COLORS[rule.category] }}
            />
          )}
          {rule.category ? CATEGORY_LABELS[rule.category] : rule.rule_id}
          <Badge
            className={
              rule.builtin
                ? "border-edge-strong bg-surface-2 text-ink-dim"
                : "border-sky-500/30 bg-sky-500/10 text-sky-300"
            }
          >
            {rule.builtin ? "built-in" : "plug-in"}
          </Badge>
        </span>
      }
    >
      <p className="font-mono text-xs text-ink-faint">{rule.source}</p>
      {rule.description && (
        <p className="mt-2 text-sm">{rule.description}</p>
      )}
      {rule.recommended_actions.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
            Runbook when diagnosed
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink-dim">
            {rule.recommended_actions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </div>
      )}
      {rule.category && (
        <Link
          href={`/?failure_category=${encodeURIComponent(rule.category)}`}
          className="mt-3 inline-block text-sm text-accent hover:underline"
        >
          Incidents with this diagnosis →
        </Link>
      )}
    </Panel>
  );
}
