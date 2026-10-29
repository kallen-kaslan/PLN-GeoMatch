import { useQuery } from "@tanstack/react-query";
import { correctionApi, type CorrectionCheck } from "@/lib/corrections";
import type { CorrectionKind } from "@/lib/master";

export function usePdpjUpdate(kind: CorrectionKind, check?: CorrectionCheck) {
  const metadata = check?.pdpj_update;
  const query = useQuery({
    queryKey: ["correction-pdpj-update", kind, check?.process_id, metadata?.review_id, metadata?.decision_revision],
    queryFn: ({ signal }) => correctionApi.pdpjUpdate(kind, check!.process_id, signal),
    enabled: !!metadata && metadata.conflicts_checked === false,
    staleTime: Infinity,
    retry: false,
  });
  return {
    update: query.data?.review_id === metadata?.review_id ? query.data : metadata,
    pending: !!metadata && metadata.conflicts_checked === false && query.isPending,
    error: query.isError,
    retry: () => void query.refetch(),
  };
}
