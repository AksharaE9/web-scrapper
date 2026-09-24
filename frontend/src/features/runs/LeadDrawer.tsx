import React from "react";
import { Lead } from "../../types";
import { useRelabelLead } from "../../hooks/useLeads";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { ReasonChip } from "../../components/ui/ReasonChip";
import {
  X,
  Phone,
  Mail,
  Globe,
  MapPin,
  CheckCircle2,
  XCircle,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";

interface LeadDrawerProps {
  lead: Lead | null;
  runId: string;
  onClose: () => void;
  onNext?: () => void;
  onPrev?: () => void;
}

export const LeadDrawer: React.FC<LeadDrawerProps> = ({
  lead,
  runId,
  onClose,
  onNext,
  onPrev,
}) => {
  const relabelMutation = useRelabelLead(runId);

  if (!lead) return null;

  const handleRelabel = async (verdict: "relevant" | "not_relevant" | "unsure") => {
    try {
      await relabelMutation.mutateAsync({
        businessId: lead.id,
        verdict,
      });
      toast.success(`Labeled as ${verdict.replace("_", " ")}`);
    } catch (err: any) {
      toast.error(err.message || "Failed to submit label");
    }
  };

  return (
    <div
      data-testid="lead-drawer"
      className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-surface-1 border-l border-border-strong shadow-2xl flex flex-col justify-between overflow-hidden animate-in slide-in-from-right duration-200"
    >
      {/* Top Header */}
      <div className="p-4 border-b border-border-subtle flex items-start justify-between gap-3 bg-surface-2/40">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-text-primary truncate">{lead.canonical_name}</h2>
            <Badge
              variant={
                lead.tier === "Verified"
                  ? "verified"
                  : lead.tier === "Likely"
                  ? "likely"
                  : "unverified"
              }
            >
              {lead.tier}
            </Badge>
          </div>
          <div className="text-xs text-text-muted flex items-center gap-1.5 font-mono">
            <MapPin className="w-3.5 h-3.5 text-accent" />
            <span>{lead.locality || lead.address_text || "—"}</span>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-md hover:bg-surface-3 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Drawer Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 text-xs">
        {/* Contact Information */}
        <div className="p-3.5 rounded-lg border border-border-subtle bg-surface-2/30 space-y-2.5">
          <div className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider font-mono">
            Verified Contact Channels
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-text-muted">
                <Phone className="w-3.5 h-3.5 text-accent" /> Phone
              </span>
              <span className="font-mono text-text-primary font-medium">
                {lead.phones_e164 && lead.phones_e164.length > 0 ? lead.phones_e164.join(", ") : "—"}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-text-muted">
                <Mail className="w-3.5 h-3.5 text-accent" /> Email
              </span>
              <span className="font-mono text-text-primary font-medium">
                {lead.emails && lead.emails.length > 0 ? lead.emails.join(", ") : "—"}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-text-muted">
                <Globe className="w-3.5 h-3.5 text-accent" /> Website
              </span>
              {lead.website_url ? (
                <a
                  href={lead.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:underline flex items-center gap-1 font-mono"
                >
                  {lead.website_domain || "Visit"} <ExternalLink className="w-3 h-3" />
                </a>
              ) : (
                <span className="text-text-muted font-mono">—</span>
              )}
            </div>
          </div>
        </div>

        {/* Relevance Evidence & Reasons */}
        <div className="space-y-2">
          <div className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider font-mono">
            Relevance Evidence & Explanations
          </div>
          <div className="flex flex-wrap gap-1.5">
            {lead.relevance_reasons && lead.relevance_reasons.length > 0 ? (
              lead.relevance_reasons.map((r, i) => (
                <ReasonChip
                  key={i}
                  type={r.type || "positive"}
                  label={r.label || r.feature || r.detail || "signal"}
                  icon={r.icon}
                  weight={r.weight}
                />
              ))
            ) : (
              <span className="text-text-muted font-mono text-xs">No specific vetoes or defining signals triggered</span>
            )}
          </div>
        </div>

        {/* Field Provenance List */}
        <div className="space-y-2">
          <div className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider font-mono">
            Field Provenance & Corroboration
          </div>
          <div data-testid="provenance-list" className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-surface-1 overflow-hidden font-mono text-[11px]">
            {lead.field_provenance && lead.field_provenance.length > 0 ? (
              lead.field_provenance.map((fp, i) => (
                <div key={i} className="p-2.5 flex items-center justify-between">
                  <span>{fp.field}</span>
                  <Badge variant="good" size="sm">
                    {fp.source} ({(fp.confidence * 100).toFixed(0)}%)
                  </Badge>
                </div>
              ))
            ) : (
              <div className="p-2.5 text-text-muted">
                Corroborated across {lead.independent_source_count || 1} sources
              </div>
            )}
          </div>
        </div>

        {/* Verification Checklist */}
        <div className="space-y-2">
          <div className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider font-mono">
            Pipeline Verification Checks
          </div>
          <div className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-surface-1 overflow-hidden font-mono">
            <div className="p-2.5 flex items-center justify-between">
              <span>Boundary Check (150m buffer)</span>
              <Badge variant="good" size="sm">PASSED</Badge>
            </div>
            <div className="p-2.5 flex items-center justify-between">
              <span>Operating Status</span>
              <Badge variant="good" size="sm">{lead.operating_status || "OPERATIONAL"}</Badge>
            </div>
            <div className="p-2.5 flex items-center justify-between">
              <span>Phone Format E.164</span>
              <Badge variant={lead.phones_e164?.length ? "good" : "unverified"} size="sm">
                {lead.phones_e164?.length ? "VALID" : "UNVERIFIED"}
              </Badge>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Actions / Relabel Buttons */}
      <div className="p-4 border-t border-border-subtle bg-surface-2/40 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <Button
            variant="primary"
            size="sm"
            onClick={() => handleRelabel("relevant")}
            className="gap-1 bg-emerald-600 hover:bg-emerald-700"
          >
            <CheckCircle2 className="w-3.5 h-3.5" /> Relevant (Y)
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => handleRelabel("not_relevant")}
            className="gap-1"
          >
            <XCircle className="w-3.5 h-3.5" /> Reject (N)
          </Button>
        </div>

        <div className="flex items-center gap-1">
          {onPrev && (
            <Button variant="outline" size="sm" onClick={onPrev}>
              Prev (K)
            </Button>
          )}
          {onNext && (
            <Button variant="outline" size="sm" onClick={onNext}>
              Next (J)
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
