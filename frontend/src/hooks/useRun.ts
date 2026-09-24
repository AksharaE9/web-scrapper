import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { qk } from "../lib/queryKeys";

export function useRun(runId: string | null) {
  return useQuery({
    queryKey: qk.run(runId),
    queryFn: () => {
      if (!runId) throw new Error("No runId provided");
      return api.getRun(runId);
    },
    enabled: !!runId,
    staleTime: 10000,
  });
}
