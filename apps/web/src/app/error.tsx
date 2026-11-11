"use client";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-md py-16 text-center" role="alert">
      <p className="font-mono text-5xl text-ink-faint">:(</p>
      <h1 className="mt-3 text-lg font-semibold">Something broke</h1>
      <p className="mt-2 break-words text-sm text-ink-dim">
        {error.message || "An unexpected error occurred."}
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-6 rounded border border-edge-strong bg-surface-2 px-4 py-2 text-sm hover:border-accent"
      >
        Try again
      </button>
    </div>
  );
}
