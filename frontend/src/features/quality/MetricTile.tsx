import React from "react";
import { Badge } from "../../components/ui/Badge";
import { formatPercent } from "../../lib/format";
import { ShieldCheck, HelpCircle } from "lucide-react";

export type MetricKind = "measured" | "proxy" | "insufficient";

interface MetricTileProps {
  label: string;
  value?: number;
  kind: MetricKind;
  sampleSize?: number;
  wilsonInterval?: { lower: number; upper: number };
  requiredLabels?: number;
}

export const MetricTile: React.FC<MetricTileProps> = ({
  label,
  value,
  kind,
  sampleSize = 0,
  wilsonInterval,
  requiredLabels = 30,
}) => {
  const isInsufficient = kind === "insufficient" || sampleSize < requiredLabels;

  return (
    <div className="p-4 rounded-lg border border-border-subtle bg-surface-1 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-text-secondary">{label}</span>
        {isInsufficient ? (
          <Badge variant="warning" size="sm" className="text-[10px]">
            INSUFFICIENT LABELS
          </Badge>
        ) : kind === "measured" ? (
          <Badge variant="good" size="sm" className="text-[10px] gap-1">
            <ShieldCheck className="w-3 h-3" /> MEASURED
          </Badge>
        ) : (
          <Badge variant="likely" size="sm" className="text-[10px] gap-1">
            <HelpCircle className="w-3 h-3" /> ESTIMATE
          </Badge>
        )}
      </div>

      <div className="my-3">
        {isInsufficient ? (
          <div className="space-y-1">
            <div className="text-lg font-bold text-text-muted font-mono">—</div>
            <div className="text-[11px] text-amber-500 font-medium">
              Label {Math.max(0, requiredLabels - sampleSize)} more to unlock
            </div>
          </div>
        ) : (
          <div className="space-y-0.5">
            <div className="text-2xl font-bold font-mono text-text-primary tracking-tight">
              {formatPercent(value)}
            </div>
            {wilsonInterval && (
              <div className="text-[11px] font-mono text-text-muted">
                95% CI: [{formatPercent(wilsonInterval.lower)}, {formatPercent(wilsonInterval.upper)}] (n={sampleSize})
              </div>
            )}
          </div>
        )}
      </div>

      <div className="text-[10px] font-mono text-text-muted border-t border-border-subtle pt-2">
        {isInsufficient ? `Ground truth sample size: ${sampleSize}` : `Evaluated across ${sampleSize} verified ground truth labels`}
      </div>
    </div>
  );
};
