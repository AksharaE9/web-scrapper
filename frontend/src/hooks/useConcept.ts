import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { qk } from "../lib/queryKeys";
import { ConceptCard } from "../types";

export function useConcept(keyword: string | null) {
  return useQuery({
    queryKey: qk.concept(keyword || ""),
    queryFn: () => {
      if (!keyword) throw new Error("Keyword is required");
      return api.getConceptCard(keyword);
    },
    enabled: !!keyword,
    staleTime: 300000, // 5 min
  });
}

export function useUpdateConcept() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ conceptId, card }: { conceptId: string; card: Partial<ConceptCard> }) =>
      api.updateConceptCard(conceptId, card),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: qk.concept(variables.conceptId) });
    },
  });
}
