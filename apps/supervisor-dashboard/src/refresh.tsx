import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
interface RefreshState {
  tick: number;
  intervalMs: number;
  lastSync: Date | null;
  setIntervalMs: (ms: number) => void;
  sync: () => void;
}
const RefreshContext = createContext<RefreshState | null>(null);
export function RefreshProvider({ children }: { children: ReactNode }) {
  const [tick, setTick] = useState(0);
  const [intervalMs, setIntervalMs] = useState(15000);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const sync = useCallback(() => {
    setTick((t) => t + 1);
    setLastSync(new Date());
  }, []);
  useEffect(() => {
    if (intervalMs <= 0) return;
    const id = setInterval(sync, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs, sync]);
  const value = useMemo(
    () => ({ tick, intervalMs, lastSync, setIntervalMs, sync }),
    [tick, intervalMs, lastSync, sync]
  );
  return <RefreshContext.Provider value={value}>{children}</RefreshContext.Provider>;
}
export function useRefresh(): RefreshState {
  const ctx = useContext(RefreshContext);
  if (!ctx) throw new Error("useRefresh must be used inside <RefreshProvider>");
  return ctx;
}
/**
 * Stale-while-revalidate polling.
 * - Re-fetches on every global refresh tick WITHOUT clearing current data
 *   (no flicker, no lost scroll position, no remounts).
 * - Resets to loading state only when `deps` change (e.g. a filter switch).
 */
export function usePoll<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const { tick } = useRefresh();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const depsKey = JSON.stringify(deps);
  useEffect(() => {
    setData(null);
    setLoading(true);
  }, [depsKey]);
  useEffect(() => {
    let alive = true;
    fetcher()
      .then((d) => {
        if (!alive) return;
        setData(d);
        setError(null);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, depsKey]);
  return { data, error, loading };
}
