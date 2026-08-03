"use client";

import { useEffect, useRef, useState } from "react";
import { copyText } from "@/lib/export";

export function CopyButton({
  text,
  label,
  className = "",
}: {
  text: string;
  label: string;
  className?: string;
}) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const handleCopy = async () => {
    const ok = await copyText(text);
    setState(ok ? "copied" : "failed");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={`rounded border border-edge-strong bg-surface-2 px-3 py-1.5 text-sm hover:border-accent ${className}`}
    >
      {state === "idle" && label}
      {state === "copied" && "✓ Copied"}
      {state === "failed" && "Copy unavailable — select the text manually"}
    </button>
  );
}
