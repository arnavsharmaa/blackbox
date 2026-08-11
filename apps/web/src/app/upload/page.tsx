"use client";

import { useState } from "react";
import Link from "next/link";
import type { UploadResponse } from "@blackbox/schemas";
import {
  ApiError,
  uploadIncident,
  type UploadErrorDetail,
} from "@/lib/api";
import { CATEGORY_LABELS, confidencePct } from "@/lib/format";
import { Panel } from "@/components/ui";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [metadata, setMetadata] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setResult(null);
    setError(null);
    try {
      setResult(await uploadIncident(file, metadata));
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0));
    } finally {
      setBusy(false);
    }
  };

  const detail = errorDetail(error);

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Upload an incident</h1>
        <p className="mt-1 text-sm text-ink-dim">
          Accepts a full incident <span className="font-mono">.json</span>, a
          normalized <span className="font-mono">.csv</span> event stream, or
          a ROS 2 <span className="font-mono">.mcap</span> bag. CSV and MCAP
          uploads need a metadata JSON with at least{" "}
          <span className="font-mono">id</span> and{" "}
          <span className="font-mono">robot_id</span>.
        </p>
      </div>

      <Panel>
        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              Incident file
            </span>
            <input
              type="file"
              accept=".json,.csv,.mcap"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="block w-full cursor-pointer rounded border border-edge bg-surface-2 text-sm file:mr-3 file:cursor-pointer file:rounded-l file:border-0 file:bg-surface-0 file:px-3 file:py-2 file:text-sm file:text-ink"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              Metadata JSON (optional for .json uploads)
            </span>
            <textarea
              value={metadata}
              onChange={(event) => setMetadata(event.target.value)}
              rows={4}
              spellCheck={false}
              placeholder='{"id": "INC-BAG-001", "robot_id": "W-104"}'
              className="w-full rounded border border-edge bg-surface-2 px-2 py-1.5 font-mono text-xs focus:border-accent"
            />
          </label>
          <button
            type="submit"
            disabled={!file || busy}
            className="rounded border border-edge-strong bg-surface-2 px-4 py-2 text-sm font-medium hover:border-accent disabled:opacity-40 disabled:hover:border-edge-strong"
          >
            {busy ? "Uploading…" : "Upload and analyze"}
          </button>
        </form>
      </Panel>

      {result && (
        <div
          role="status"
          className="rounded-lg border border-emerald-500/40 bg-emerald-950/20 p-4"
        >
          <p className="text-sm font-medium text-emerald-300">
            Incident ingested and analyzed
          </p>
          <p className="mt-1 text-sm text-ink-dim">
            {result.event_count} events, {result.telemetry_channels} telemetry
            channels — diagnosed{" "}
            <span className="text-ink">
              {CATEGORY_LABELS[result.failure_category]}
            </span>{" "}
            at {confidencePct(result.confidence)} confidence.
          </p>
          <Link
            href={`/incidents/${encodeURIComponent(result.incident_id)}`}
            className="mt-2 inline-block rounded border border-emerald-500/50 bg-emerald-500/10 px-3 py-1.5 text-sm text-emerald-300 hover:border-emerald-400"
          >
            Open {result.incident_id} →
          </Link>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-500/40 bg-red-950/20 p-4"
        >
          <p className="text-sm font-medium text-red-300">
            {detail?.message ?? error.message}
          </p>
          {detail && detail.errors.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-ink-dim">
              {detail.errors.map((item) => (
                <li key={`${item.field}-${item.error}`}>
                  <span className="font-mono text-xs text-red-300">
                    {item.field}
                  </span>{" "}
                  — {item.error}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function errorDetail(error: ApiError | null): UploadErrorDetail | null {
  if (!error || typeof error.detail !== "object" || error.detail === null) {
    return null;
  }
  const candidate = error.detail as Partial<UploadErrorDetail>;
  if (typeof candidate.message !== "string") return null;
  return {
    message: candidate.message,
    errors: Array.isArray(candidate.errors)
      ? candidate.errors.filter(
          (item): item is { field: string; error: string } =>
            typeof item === "object" &&
            item !== null &&
            typeof (item as { field?: unknown }).field === "string" &&
            typeof (item as { error?: unknown }).error === "string",
        )
      : [],
  };
}
