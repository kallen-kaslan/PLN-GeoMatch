import { useQuery, useQueryClient } from "@tanstack/react-query";
import { correctionApi, type CorrectionRun, type MapRadiusSummary } from "@/lib/corrections";
import type { CorrectionKind } from "@/lib/master";

export function useMapRadiusSummary(kind: CorrectionKind, process: number | undefined, run: CorrectionRun | undefined, radius: number | null, enabled: boolean) {
  const client = useQueryClient();
  const queryKey = ["correction-map-summary", kind, process, run?.generation, radius];
  return useQuery({ queryKey, enabled: enabled && !!process && !!run && radius !== null,
    queryFn: async ({ signal }) => {
      const response = await correctionApi.mapSummary(kind, process!, run!.generation, radius!, signal);
      const previous = client.getQueryData<MapRadiusSummary>(queryKey);
      return previous && previous.revision > response.revision ? previous : response;
    }, staleTime: 30_000 });
}
