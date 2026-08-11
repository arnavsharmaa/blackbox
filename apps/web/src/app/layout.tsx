import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "BlackBox — Robot Incident Reconstruction",
  description:
    "Flight recorder and incident reconstruction platform for autonomous robots",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <header className="sticky top-0 z-40 border-b border-edge bg-surface-0/95 backdrop-blur">
          <div className="mx-auto flex h-12 max-w-[1600px] items-center gap-6 px-4">
            <Link href="/" className="flex items-center gap-2">
              <span
                aria-hidden
                className="inline-block h-3 w-3 rounded-sm bg-accent shadow-[0_0_8px_rgba(245,158,11,0.6)]"
              />
              <span className="text-sm font-semibold tracking-wide">
                BlackBox
              </span>
              <span className="hidden text-xs text-ink-faint sm:inline">
                robot incident reconstruction
              </span>
            </Link>
            <nav className="ml-auto flex items-center gap-4 text-sm text-ink-dim">
              <Link href="/" className="hover:text-ink">
                Incidents
              </Link>
              <Link href="/analytics" className="hover:text-ink">
                Analytics
              </Link>
              <Link href="/upload" className="hover:text-ink">
                Upload
              </Link>
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/docs`}
                target="_blank"
                rel="noreferrer"
                className="hover:text-ink"
              >
                API docs
              </a>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-[1600px] px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
