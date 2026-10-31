import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { newestCheckpoint, type ProcessActivity } from "@/lib/progress";

export function useProcessMonitor<T extends { activity?: ProcessActivity }>({ queryKey, queryFn, checkpoint, revision, enabled, publish }: {
  queryKey: readonly unknown[]; queryFn: () => Promise<T>; checkpoint: T;
  revision: (value: T) => number; enabled: boolean;
  publish: (value: T, refresh: boolean) => Promise<void>;
}) {
  const query = useQuery({ queryKey, queryFn, enabled, refetchInterval: enabled ? 2000 : false, refetchIntervalInBackground: true, retry: false });
  useEffect(() => {
    if (query.data && query.data !== checkpoint && newestCheckpoint(checkpoint, query.data, revision) === query.data) {
      void publish(query.data, revision(query.data) !== revision(checkpoint));
    }
  }, [query.data, checkpoint, revision, publish]);
  return query;
}
