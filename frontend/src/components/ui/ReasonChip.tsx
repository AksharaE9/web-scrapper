import React from "react";
import { cn } from "../../lib/cn";
import { Check, X, AlertCircle } from "lucide-react";
import { ChipDescriptor } from "../../types";
import { renderSafe } from "../../lib/renderSafe";

export interface ReasonChipProps extends Partial<ChipDescriptor> {
  label: string | any;
  className?: string;
  onClick?: () => void;
}

export function ReasonChip({ type = "positive", label, icon, weight, className, onClick }: ReasonChipProps) {
  const isPos = type === "positive" || type === "good";
  const isNeg = type === "negative" || type === "veto" || type === "critical";

  let renderedIcon: React.ReactNode = null;
  if (React.isValidElement(icon)) {
    renderedIcon = icon;
  } else if (typeof icon === "string") {
    if (icon === "✓" || icon === "check") renderedIcon = <Check className="w-3 h-3 text-emerald-500 shrink-0" />;
    else if (icon === "✗" || icon === "cross") renderedIcon = <X className="w-3 h-3 text-rose-500 shrink-0" />;
    else renderedIcon = <span className="text-[10px] shrink-0">{icon}</span>;
  } else {
    renderedIcon = isPos ? (
      <Check className="w-3 h-3 text-emerald-500 shrink-0" />
    ) : isNeg ? (
      <X className="w-3 h-3 text-rose-500 shrink-0" />
    ) : (
      <AlertCircle className="w-3 h-3 text-text-muted shrink-0" />
    );
  }

  const safeLabel =
    typeof label === "object" && label !== null
      ? label.label || label.name || label.feature || label.detail || label.unexpected || "signal"
      : label || "signal";

  return (
    <span
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium border transition-colors",
        isPos && "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
        isNeg && "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
        !isPos && !isNeg && "bg-surface-2 text-text-secondary border-border-subtle",
        onClick && "cursor-pointer hover:border-border-strong",
        className
      )}
    >
      {renderedIcon}
      <span>{renderSafe(safeLabel, "ReasonChip.label")}</span>
      {weight !== undefined && (
        <span className="text-[10px] opacity-70">
          ({weight > 0 ? `+${weight.toFixed(1)}` : weight.toFixed(1)})
        </span>
      )}
    </span>
  );
}

