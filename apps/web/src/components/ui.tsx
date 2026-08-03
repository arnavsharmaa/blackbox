import type { ReactNode } from "react";

export function Panel({
  title,
  actions,
  children,
  className = "",
}: {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-lg border border-edge bg-surface-1 ${className}`}
    >
      {(title || actions) && (
        <header className="flex items-center justify-between border-b border-edge px-4 py-2.5">
          {title && (
            <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-dim">
              {title}
            </h2>
          )}
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Badge({
  children,
  className = "",
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium leading-4 ${className}`}
    >
      {children}
    </span>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      role="status"
      className="flex items-center justify-center gap-3 rounded-lg border border-edge bg-surface-1 py-16 text-sm text-ink-dim"
    >
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-edge-strong border-t-accent" />
      {label}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: Error;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-500/40 bg-red-950/20 px-6 py-8 text-center"
    >
      <p className="text-sm font-medium text-red-300">Something went wrong</p>
      <p className="mx-auto mt-1 max-w-lg text-sm text-ink-dim">
        {error.message}
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded border border-edge-strong bg-surface-2 px-3 py-1.5 text-sm hover:border-accent"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  hint,
}: {
  title: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-dashed border-edge px-6 py-12 text-center">
      <p className="text-sm font-medium text-ink-dim">{title}</p>
      {hint && <p className="mt-1 text-sm text-ink-faint">{hint}</p>}
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className="rounded-lg border border-edge bg-surface-1 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
        {label}
      </p>
      <p
        className={`mt-1 text-2xl font-semibold tabular-nums ${accent ? "text-accent" : ""}`}
      >
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-ink-dim">{sub}</p>}
    </div>
  );
}
