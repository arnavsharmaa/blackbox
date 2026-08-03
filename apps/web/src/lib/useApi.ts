"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

/** Minimal fetch hook with loading/error state and manual refetch. */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: readonly unknown[],
): ApiState<T> & { refetch: () => void } {
  const [state, setState] = useState<ApiState<T>>({
    data: null,
    loading: true,
    error: null,
  });
  const generation = useRef(0);

  const load = useCallback(() => {
    const current = ++generation.current;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    fetcher()
      .then((data) => {
        if (generation.current === current) {
          setState({ data, loading: false, error: null });
        }
      })
      .catch((error: Error) => {
        if (generation.current === current) {
          setState({ data: null, loading: false, error });
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  // Stale responses are discarded by the generation check inside load(),
  // so no unmount cleanup is required.
  useEffect(() => {
    load();
  }, [load]);

  return { ...state, refetch: load };
}
