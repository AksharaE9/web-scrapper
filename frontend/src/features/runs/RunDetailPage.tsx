import React, { useState, useEffect } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { useRun } from "../../hooks/useRun";
import { useLeads } from "../../hooks/useLeads";
import { api } from "../../api/client";
import { Lead } from "../../types";
import { DecisionTabs } from "./DecisionTabs";
import { LeadsTable } from "./LeadsTable";
import { LeadDrawer } from "./LeadDrawer";
import { ReviewQueue } from "./ReviewQueue";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { Skeleton, ErrorState } from "../../components/ui/EmptyState";
import { SectionErrorBoundary } from "../../components/ui/ErrorBoundary";
import { renderSafe } from "../../lib/renderSafe";
import {
  Download,
  RotateCcw,
  ArrowLeft,
  MapPin,
  Tag,
  Clock,
  ListChecks,
  Info,
} from "lucide-react";
import { formatDate } from "../../lib/format";
import { CompletionBanner } from "../../components/ui/CompletionBanner";
import { SourceFunnel } from "./SourceFunnel";

export const RunDetailPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const tabParam = searchParams.get("tab");
  const initialTab = (tabParam === "review" || tabParam === "rejected") ? tabParam : "accepted";
  const [activeTab, setActiveTab] = useState<"accepted" | "review" | "rejected">(initialTab);

  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [isReviewQueueMode, setIsReviewQueueMode] = useState(false);
  const [rescoring, setRescoring] = useState(false);

  const { data: run, isLoading: runLoading, isError: runError, error } = useRun(runId || null);
  const { data: leadsResponse, isLoading: leadsLoading, isError: leadsError, error: leadsErr, refetch: refetchLeads } = useLeads(runId || null, { decision: activeTab });

  useEffect(() => {
    if (tabParam && (tabParam === "accepted" || tabParam === "review" || tabParam === "rejected")) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  const handleTabChange = (tab: "accepted" | "review" | "rejected") => {
    setActiveTab(tab);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("tab", tab);
      return next;
    });
  };

  if (runLoading) {
    return (
      <div className="max-w-6xl mx-auto space-y-4">
        <Skeleton className="h-16 w-full rounded-lg" />
        <Skeleton className="h-96 w-full rounded-lg" />
      </div>
    );
  }

  if (runError || !run) {
    return (
      <div className="max-w-4xl mx-auto py-8">
        <ErrorState error={error as Error} title="Run Not Found" />
      </div>
    );
  }

  const currentTabLeads = leadsResponse?.items || [];
  const total = leadsResponse?.total ?? currentTabLeads.length;
  const counts = leadsResponse?.counts ?? {
    accepted: activeTab === "accepted" ? currentTabLeads.length : 0,
    review: activeTab === "review" ? currentTabLeads.length : 0,
    rejected: activeTab === "rejected" ? currentTabLeads.length : 0,
  };

  const isExhausted = run.completion_reason === "region_exhausted";

  const handleRescore = async () => {
    if (!runId) return;
    setRescoring(true);
    try {
      await api.rescoreRun(runId);
      toast.success("Rescored run decisions against latest concept cards!");
      refetchLeads();
    } catch (err: any) {
      toast.error(err.message || "Failed to rescore");
    } finally {
      setRescoring(false);
    }
  };

  if (isReviewQueueMode) {
    return (
      <ReviewQueue
        leads={currentTabLeads}
        runId={run.id}
        onExit={() => setIsReviewQueueMode(false)}
      />
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-5 pb-16">
      {/* Top Breadcrumb & Header */}
      <div>
        <Link
          to="/runs"
          className="text-xs text-text-muted hover:text-text-primary inline-flex items-center gap-1 mb-2 font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Runs
        </Link>

        <div className="p-4 rounded-lg border border-border-subtle bg-surface-1 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-text-primary flex items-center gap-1.5">
                <MapPin className="w-4 h-4 text-accent shrink-0" />
                {renderSafe(run.locality || run.geo_display_name || "Target Locality", "RunHeader.locality")}
              </h1>
              <Badge
                data-testid="run-status"
                variant={run.status === "completed" ? "good" : run.status === "partial" ? "warning" : "critical"}
                size="sm"
                className="font-mono text-[10px]"
              >
                {run.status.toUpperCase()}
              </Badge>
              {run.completion_reason && (
                <span
                  data-testid="completion-reason"
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20"
                >
                  {run.completion_reason}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-text-muted font-mono">
              <span className="flex items-center gap-1"><Tag className="w-3 h-3" /> {(run.keywords || []).join(", ")}</span>
              <span>·</span>
              <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {formatDate(run.created_at)}</span>
            </div>
          </div>

          {/* Actions: Export & Review Queue */}
          <div className="flex items-center gap-2">
            {counts.review > 0 && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  if (activeTab !== "review") handleTabChange("review");
                  setIsReviewQueueMode(true);
                }}
                className="gap-1.5 bg-amber-600 hover:bg-amber-700 text-white shadow-sm"
              >
                <ListChecks className="w-3.5 h-3.5" /> Start Review Queue ({counts.review})
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={handleRescore}
              disabled={rescoring}
              className="gap-1.5"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${rescoring ? "animate-spin" : ""}`} /> Rescore
            </Button>

            <a
              href={api.getExportUrl(run.id, "csv", activeTab)}
              download
              title={`Export ${counts[activeTab]} ${activeTab} leads as CSV (delivered and suppressed excluded)`}
            >
              <Button variant="secondary" size="sm" className="gap-1.5">
                <Download className="w-3.5 h-3.5" /> CSV ({counts[activeTab]})
              </Button>
            </a>

            <a
              href={api.getExportUrl(run.id, "xlsx", activeTab)}
              download
              title={`Export ${counts[activeTab]} ${activeTab} leads as Excel (XLSX)`}
            >
              <Button variant="secondary" size="sm" className="gap-1.5">
                <Download className="w-3.5 h-3.5" /> Excel ({counts[activeTab]})
              </Button>
            </a>
          </div>
        </div>
      </div>

      {/* Per-Source Funnel & Telemetry */}
      <SourceFunnel
        sourceStats={(run.stats as any)?.source_stats}
        keywords={run.keywords}
        locality={run.locality || run.geo_display_name}
        onRefreshRun={() => window.location.reload()}
      />

      {/* Reason-Specific Truth-Telling Banner (§2.2) */}
      <CompletionBanner
        reason={run.completion_reason || (run.status === "completed" && counts.accepted < ((run as any).raw_input?.max_results || 50) ? "low_relevance" : null)}
        acceptedCount={counts.accepted}
        targetCount={(run as any).raw_input?.max_results || 50}
        details={(run.stats as any)?.completion_details || (run.stats as any)?.dedup || {}}
        locality={run.locality || run.geo_display_name || "this area"}
        keyword={(run.keywords || [])[0] || "business"}
        reviewCount={counts.review}
        onReviewBorderline={() => handleTabChange("review")}
        onViewExisting={() => handleTabChange("accepted")}
        onWidenArea={() => {
          window.location.href = "/scrape";
        }}
      />

      {/* Decision Tabs */}
      <DecisionTabs
        activeTab={activeTab}
        onTabChange={handleTabChange}
        counts={counts}
      />

      {/* Pagination & Count Indicator (§4) */}
      <div className="flex items-center justify-between text-xs font-mono text-text-muted px-1">
        {total > currentTabLeads.length ? (
          <span data-testid="pagination-notice">Showing {currentTabLeads.length} of {total}</span>
        ) : currentTabLeads.length === total ? (
          <span>Showing all {total} {activeTab} leads</span>
        ) : (
          <span data-testid="mismatch-notice" className="text-amber-400">
            Showing {currentTabLeads.length} of {total} — {total - currentTabLeads.length} rows could not be displayed
          </span>
        )}
      </div>

      {/* Leads Table wrapped in SectionErrorBoundary */}
      <SectionErrorBoundary context="LeadsTableSection" metadata={{ runId: run.id, activeTab }}>
        <LeadsTable
          leads={currentTabLeads}
          selectedLeadId={selectedLead?.id || null}
          onSelectLead={setSelectedLead}
          isLoading={leadsLoading}
          isError={leadsError}
          error={leadsErr as Error}
          activeTab={activeTab}
          onSwitchTab={handleTabChange}
        />
      </SectionErrorBoundary>

      {/* Lead Drawer */}
      {selectedLead && (
        <LeadDrawer
          lead={selectedLead}
          runId={run.id}
          onClose={() => setSelectedLead(null)}
        />
      )}
    </div>
  );
};
