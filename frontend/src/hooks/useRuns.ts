import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { qk, RunFilters } from "../lib/queryKeys";

export function useRuns(filters?: RunFilters) {
  return useQuery({
    queryKey: qk.runs(filters),
    queryFn: () => api.listRuns(),
    staleTime: 30000,
    refetchOnWindowFocus: true,
  });
}
