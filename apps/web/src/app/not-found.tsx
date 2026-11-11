import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <p className="font-mono text-5xl text-ink-faint">404</p>
      <h1 className="mt-3 text-lg font-semibold">
        No flight data at this address
      </h1>
      <p className="mt-2 text-sm text-ink-dim">
        The page doesn&apos;t exist — the incident may have been deleted or
        the link mistyped.
      </p>
      <Link
        href="/"
        className="mt-6 inline-block rounded border border-edge-strong bg-surface-2 px-4 py-2 text-sm hover:border-accent"
      >
        Back to the incident overview
      </Link>
    </div>
  );
}
