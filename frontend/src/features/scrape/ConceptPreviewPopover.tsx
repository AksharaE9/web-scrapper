import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { qk } from "../../lib/queryKeys";
import { Badge } from "../../components/ui/Badge";
import { Check, X, Sparkles } from "lucide-react";

export const ConceptPreviewPopover: React.FC<{ keyword: string }> = ({ keyword }) => {
  const { data: card, isLoading } = useQuery({
    queryKey: qk.concept(keyword),
    queryFn: () => api.getConceptCard(keyword),
    staleTime: 300000,
    retry: false,
  });

  if (isLoading) {
    return <div className="p-3 text-xs text-text-muted">Loading concept card...</div>;
  }

  if (!card) {
    return (
      <div className="p-3 text-xs text-text-muted">
        No pre-seeded concept card for &quot;{keyword}&quot;. Standard NLP tokenization and ontology rules will apply.
      </div>
    );
  }

  const defTerms = card.signals?.defining_terms?.strong || [];
  const vetoTerms = card.veto_terms || [];

  return (
    <div className="p-3 space-y-2 text-xs font-mono max-w-sm">
      <div className="flex items-center justify-between border-b border-border-subtle pb-1">
        <span className="font-bold text-text-primary flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-accent" /> {card.concept_id}
        </span>
        <Badge variant="outline" size="sm">v{card.version}</Badge>
      </div>

      <div className="space-y-1">
        <div className="text-text-muted font-sans text-[11px]">{card.definition}</div>
      </div>

      {defTerms.length > 0 && (
        <div>
          <div className="text-[10px] text-emerald-500 font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
            <Check className="w-3 h-3" /> Defining Terms
          </div>
          <div className="flex flex-wrap gap-1">
            {defTerms.map((t) => (
              <span key={t} className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[10px]">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {vetoTerms.length > 0 && (
        <div>
          <div className="text-[10px] text-rose-500 font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
            <X className="w-3 h-3" /> Veto Terms
          </div>
          <div className="flex flex-wrap gap-1">
            {vetoTerms.map((t) => (
              <span key={t} className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 text-[10px]">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
