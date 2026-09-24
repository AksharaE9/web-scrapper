import React, { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Lead } from "../../types";
import { Badge } from "../../components/ui/Badge";
import { ReasonChip } from "../../components/ui/ReasonChip";
import { useUiPrefs } from "../../stores/useUiPrefs";
import { Phone, Mail, Globe, MapPin, ChevronRight } from "lucide-react";
import { RowErrorBoundary } from "../../components/ui/ErrorBoundary";
import { renderSafe } from "../../lib/renderSafe";

interface LeadsTableProps {
  leads: Lead[];
  selectedLeadId?: string | null;
  onSelectLead?: (lead: Lead) => void;
  isLoading?: boolean;
  isError?: boolean;
  error?: Error | null;
  activeTab?: string;
  onClearFilters?: () => void;
  onSwitchTab?: (tab: "accepted" | "review" | "rejected") => void;
}

const ROW_HEIGHT_COMFORTABLE = 60;
const ROW_HEIGHT_COMPACT = 44;
const VIRTUALISE_THRESHOLD = 50; // only virtualise when list is large

/** Inner row — kept as a stable component so the virtualizer doesn't remount rows */
const LeadRow = React.memo(
  ({
    lead,
    isSelected,
    isCompact,
    onSelectLead,
    style,
  }: {
    lead: Lead;
    isSelected: boolean;
    isCompact: boolean;
    onSelectLead: (l: Lead) => void;
    style: React.CSSProperties;
  }) => {
    const hasPhone = lead.phones_e164 && lead.phones_e164.length > 0;
    const hasEmail = lead.emails && lead.emails.length > 0;
    const hasWeb = !!(lead.website_url || lead.website_domain);

    const name = lead.canonical_name || lead.name || "Lead";
    const locality = lead.locality || lead.address_text || "—";
    const category = lead.primary_category || (lead.categories && lead.categories[0]) || "—";
    const contactText = lead.phones_e164?.[0] || lead.emails?.[0] || lead.website_domain || (hasPhone ? "phone" : hasEmail ? "email" : hasWeb ? "web" : "");

    return (
      <RowErrorBoundary lead={lead} isSelected={isSelected} style={style} onSelectLead={onSelectLead}>
        <div
          data-testid="lead-row"
          style={style}
          onClick={() => onSelectLead(lead)}
          className={`flex items-center gap-0 border-b border-border-subtle hover:bg-surface-2 transition-colors cursor-pointer group ${
            isSelected ? "bg-accent/5" : ""
          }`}
          role="row"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && onSelectLead(lead)}
        >
          {/* Name & Locality */}
          <div className={`${isCompact ? "py-2" : "py-3"} px-3 w-[220px] shrink-0`}>
            <div data-testid="lead-name" className="font-semibold text-text-primary truncate text-xs">
              {renderSafe(name, "LeadRow.name")}
            </div>
            <div className="text-[11px] text-text-muted truncate flex items-center gap-1">
              <MapPin className="w-3 h-3 shrink-0" />
              <span className="truncate">{renderSafe(locality, "LeadRow.locality")}</span>
            </div>
          </div>

          {/* Primary Category */}
          <div className={`${isCompact ? "py-2" : "py-3"} px-3 w-[140px] shrink-0 text-text-secondary truncate font-mono text-[11px]`}>
            {renderSafe(category, "LeadRow.category")}
          </div>

          {/* Reason Chips */}
          <div className={`${isCompact ? "py-2" : "py-3"} px-3 flex-1 min-w-0`}>
            <div className="flex flex-wrap gap-1 max-w-[260px]">
              {lead.relevance_reasons && Array.isArray(lead.relevance_reasons) && lead.relevance_reasons.length > 0 ? (
                lead.relevance_reasons.slice(0, 2).map((r, i) => {
                  if (!r || typeof r !== "object") return null;
                  return (
                    <ReasonChip
                      key={i}
                      type={r.type || "positive"}
                      label={r.label || (r as any).feature || (r as any).detail || (r as any).unexpected || "signal"}
                      icon={r.icon}
                      weight={r.weight}
                    />
                  );
                })
              ) : (
                <span className="text-[10px] text-text-muted font-mono">{renderSafe(lead.reason_code || "standard", "LeadRow.reason_code")}</span>
              )}
            </div>
          </div>

          {/* Contact Signals */}
          <div data-testid="lead-contact" className={`${isCompact ? "py-2" : "py-3"} px-3 w-28 shrink-0`}>
            <div className="flex items-center gap-2 text-text-muted">
              <Phone className={`w-3.5 h-3.5 ${hasPhone ? "text-emerald-500" : "opacity-25"}`} />
              <Mail className={`w-3.5 h-3.5 ${hasEmail ? "text-emerald-500" : "opacity-25"}`} />
              <Globe className={`w-3.5 h-3.5 ${hasWeb ? "text-emerald-500" : "opacity-25"}`} />
              <span className="text-[10px] font-mono text-text-secondary truncate max-w-[50px] inline-block">
                {contactText}
              </span>
            </div>
          </div>

          {/* Tier */}
          <div className={`${isCompact ? "py-2" : "py-3"} px-3 w-24 shrink-0`}>
            <Badge
              variant={
                lead.tier === "Verified"
                  ? "verified"
                  : lead.tier === "Likely"
                  ? "likely"
                  : "unverified"
              }
              size="sm"
            >
              {renderSafe(lead.tier || "Unverified", "LeadRow.tier")}
            </Badge>
          </div>

          {/* Confidence */}
          <div className={`${isCompact ? "py-2" : "py-3"} px-3 w-20 shrink-0 text-right font-mono text-xs text-text-secondary`}>
            {lead.relevance_p !== undefined
              ? `${(lead.relevance_p * 100).toFixed(0)}%`
              : lead.confidence
              ? `${(lead.confidence * 100).toFixed(0)}%`
              : "—"}
          </div>

          {/* Chevron */}
          <div className="pr-3 text-text-muted group-hover:text-accent transition-colors w-8 shrink-0 flex justify-end">
            <ChevronRight className="w-4 h-4" />
          </div>
        </div>
      </RowErrorBoundary>
    );
  }
);
LeadRow.displayName = "LeadRow";

export const LeadsTable: React.FC<LeadsTableProps> = React.memo(
  ({
    leads = [],
    selectedLeadId = null,
    onSelectLead = () => {},
    isLoading = false,
    isError = false,
    error = null,
    activeTab = "accepted",
    onClearFilters,
    onSwitchTab,
  }) => {
    const density = useUiPrefs((s) => s.density);
    const isCompact = density === "compact";
    const rowHeight = isCompact ? ROW_HEIGHT_COMPACT : ROW_HEIGHT_COMFORTABLE;

    const parentRef = useRef<HTMLDivElement>(null);
    const shouldVirtualise = leads.length > VIRTUALISE_THRESHOLD;

    const rowVirtualizer = useVirtualizer({
      count: leads.length,
      getScrollElement: () => parentRef.current,
      estimateSize: () => rowHeight,
      overscan: 10,
      enabled: shouldVirtualise,
    });

    // 1. Loading State
    if (isLoading) {
      return (
        <div className="p-12 text-center border border-border-subtle bg-surface-1 rounded-lg space-y-3 font-mono">
          <div className="inline-block w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-text-muted">Loading leads dataset...</p>
        </div>
      );
    }

    // 2. Error State
    if (isError) {
      return (
        <div className="p-8 text-center border border-rose-500/30 bg-rose-500/5 rounded-lg space-y-3">
          <p className="text-xs font-semibold text-rose-500 font-mono">
            Failed to load leads: {error?.message || "Server request timed out"}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="text-xs px-3 py-1.5 rounded bg-surface-2 hover:bg-surface-3 text-text-primary border border-border-subtle font-mono font-medium transition-colors"
          >
            Retry Fetch
          </button>
        </div>
      );
    }

    // 3. Empty Leads in Bucket / Filter Empty State
    if (leads.length === 0) {
      return (
        <div className="p-10 text-center border border-dashed border-border-strong rounded-lg bg-surface-1/40 space-y-3">
          <div className="space-y-1">
            <p className="text-sm font-semibold text-text-primary">
              No leads found in {activeTab.toUpperCase()}
            </p>
            <p className="text-xs text-text-muted max-w-md mx-auto">
              {activeTab === "accepted"
                ? "No candidates satisfied all primary category and evidence signals directly. Check the Review bucket to inspect candidates requiring second signals."
                : activeTab === "review"
                ? "No borderline candidates are currently queued for manual review."
                : "No candidates were vetoed or rejected."}
            </p>
          </div>

          <div className="flex items-center justify-center gap-2 pt-2">
            {activeTab === "accepted" && onSwitchTab && (
              <button
                onClick={() => onSwitchTab("review")}
                className="text-xs px-3 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 font-mono transition-colors"
              >
                Inspect Review Queue →
              </button>
            )}
            {onClearFilters && (
              <button
                onClick={onClearFilters}
                className="text-xs px-3 py-1 rounded bg-surface-2 hover:bg-surface-3 text-text-secondary border border-border-subtle font-mono transition-colors"
              >
                Clear Filters
              </button>
            )}
          </div>
        </div>
      );
    }

    const tableHeader = (
      <div className="flex items-center gap-0 border-b border-border-subtle bg-surface-2/60 text-text-secondary font-semibold font-mono text-[11px] uppercase tracking-wider">
        <div className="py-2.5 px-3 w-[220px] shrink-0">Business Entity</div>
        <div className="py-2.5 px-3 w-[140px] shrink-0">Category</div>
        <div className="py-2.5 px-3 flex-1 min-w-0">Relevance Reasons</div>
        <div className="py-2.5 px-3 w-20 shrink-0">Signals</div>
        <div className="py-2.5 px-3 w-24 shrink-0">Tier</div>
        <div className="py-2.5 px-3 w-20 shrink-0 text-right">Conf.</div>
        <div className="w-8 shrink-0" />
      </div>
    );

    if (!shouldVirtualise) {
      // Small list — plain render, no virtualiser overhead
      return (
        <div className="border border-border-subtle rounded-lg overflow-hidden bg-surface-1 shadow-sm">
          <div className="overflow-x-auto">
            <div role="table" className="min-w-[700px]">
              {tableHeader}
              <div role="rowgroup">
                {leads.map((lead, idx) => (
                  <LeadRow
                    key={lead.id || lead.business_id || `lead-${idx}`}
                    lead={lead}
                    isSelected={selectedLeadId === (lead.id || lead.business_id)}
                    isCompact={isCompact}
                    onSelectLead={onSelectLead}
                    style={{}}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      );
    }

    // Large list — windowed render
    return (
      <div className="border border-border-subtle rounded-lg overflow-hidden bg-surface-1 shadow-sm">
        <div className="overflow-x-auto">
          <div className="min-w-[700px]">
            {tableHeader}
            <div
              ref={parentRef}
              className="overflow-y-auto"
              style={{ maxHeight: "560px" }}
              role="rowgroup"
            >
              <div
                style={{
                  height: `${rowVirtualizer.getTotalSize()}px`,
                  position: "relative",
                }}
              >
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const lead = leads[virtualRow.index];
                  return (
                    <LeadRow
                      key={lead.id}
                      lead={lead}
                      isSelected={selectedLeadId === lead.id}
                      isCompact={isCompact}
                      onSelectLead={onSelectLead}
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        width: "100%",
                        transform: `translateY(${virtualRow.start}px)`,
                        height: `${rowHeight}px`,
                      }}
                    />
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
);
LeadsTable.displayName = "LeadsTable";
