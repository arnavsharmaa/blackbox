"use client";

import { use, useState } from "react";
import Link from "next/link";
import { fetchGithubIssue } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { downloadFile } from "@/lib/export";
import { Badge, ErrorState, LoadingState } from "@/components/ui";
import { CopyButton } from "@/components/CopyButton";

const DEFAULT_REPO = process.env.NEXT_PUBLIC_GITHUB_REPO ?? "";

export default function IssuePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [repoInput, setRepoInput] = useState(DEFAULT_REPO);
  const [repo, setRepo] = useState(DEFAULT_REPO);
  const issue = useApi(
    () => fetchGithubIssue(id, repo || undefined),
    [id, repo],
  );

  if (issue.loading) return <LoadingState label="Generating issue…" />;
  if (issue.error)
    return <ErrorState error={issue.error} onRetry={issue.refetch} />;
  const data = issue.data;
  if (!data) return null;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
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
        {" / GitHub issue"}
      </nav>

      <div className="rounded-lg border border-edge bg-surface-1 p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setRepo(repoInput.trim());
            }}
          >
            <label className="block text-sm">
              <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
                Target repository (owner/repo)
              </span>
              <input
                value={repoInput}
                onChange={(e) => setRepoInput(e.target.value)}
                placeholder="acme/warehouse-robots"
                className="w-64 rounded border border-edge bg-surface-2 px-2 py-1.5 font-mono text-sm focus:border-accent"
              />
            </label>
            <button
              type="submit"
              className="rounded border border-edge-strong bg-surface-2 px-3 py-1.5 text-sm hover:border-accent"
            >
              Update URL
            </button>
          </form>
          <div className="flex gap-2">
            <CopyButton text={data.markdown} label="Copy Markdown" />
            <button
              type="button"
              onClick={() =>
                downloadFile(`${id}-issue.md`, data.markdown, "text/markdown")
              }
              className="rounded border border-edge-strong bg-surface-2 px-3 py-1.5 text-sm hover:border-accent"
            >
              Download .md
            </button>
            {data.issue_url ? (
              <a
                href={data.issue_url}
                target="_blank"
                rel="noreferrer"
                className="rounded border border-emerald-500/50 bg-emerald-500/10 px-3 py-1.5 text-sm text-emerald-300 hover:border-emerald-400"
              >
                Open prefilled issue ↗
              </a>
            ) : (
              <span
                className="cursor-not-allowed rounded border border-edge px-3 py-1.5 text-sm text-ink-faint"
                title="Enter an owner/repo above to build a prefilled GitHub URL"
              >
                Open prefilled issue
              </span>
            )}
          </div>
        </div>
        {!data.issue_url && (
          <p className="mt-2 text-xs text-ink-faint">
            No target repository set — the Markdown below can still be copied
            into any tracker.
          </p>
        )}
      </div>

      <div className="rounded-lg border border-edge bg-surface-1">
        <header className="space-y-2 border-b border-edge px-5 py-4">
          <h1 className="text-base font-semibold">{data.title}</h1>
          <div className="flex flex-wrap gap-1.5">
            {data.labels.map((label) => (
              <Badge
                key={label}
                className="border-edge-strong bg-surface-2 text-ink-dim"
              >
                {label}
              </Badge>
            ))}
          </div>
        </header>
        <pre className="panel-scroll max-h-[600px] overflow-auto whitespace-pre-wrap px-5 py-4 font-mono text-xs leading-relaxed text-ink-dim">
          {data.body}
        </pre>
      </div>
    </div>
  );
}
