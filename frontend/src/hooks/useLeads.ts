import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { qk, LeadFilters } from "../lib/queryKeys";
import { Lead, LeadsResponse } from "../types";

export function useLeads(runId: string | null, filters?: LeadFilters) {
  return useQuery<LeadsResponse>({
    queryKey: qk.leads(runId, filters),
    queryFn: () => {
      if (!runId) return { items: [], total: 0, counts: { accepted: 0, review: 0, rejected: 0 }, filters_applied: {} };
      return api.getRunLeads(runId, filters);
    },
    enabled: !!runId,
    staleTime: 15000,
  });
}

export function useRelabelLead(runId: string | null) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({
      businessId,
      verdict,
      notes,
    }: {
      businessId: string;
      verdict: "relevant" | "not_relevant" | "unsure";
      notes?: string;
    }) => {
      if (!runId) throw new Error("runId is required");
      return api.relabelLead(runId, businessId, verdict, notes);
    },
    onMutate: async ({ businessId, verdict }) => {
      await qc.cancelQueries({ queryKey: qk.leads(runId) });
      const previous = qc.getQueryData<LeadsResponse>(qk.leads(runId));

      if (previous && previous.items) {
        const newDecision = verdict === "relevant" ? ("accepted" as const) : verdict === "not_relevant" ? ("rejected" as const) : ("review" as const);
        const updatedItems = previous.items.map((lead) => {
          if (lead.id === businessId) {
            return {
              ...lead,
              decision: newDecision,
            };
          }
          return lead;
        });
        qc.setQueryData(qk.leads(runId), {
          ...previous,
          items: updatedItems,
        });
      }

      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        qc.setQueryData(qk.leads(runId), context.previous);
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: qk.leads(runId) });
      qc.invalidateQueries({ queryKey: qk.run(runId) });
      qc.invalidateQueries({ queryKey: qk.metrics("run", runId) });
    },
  });
}
