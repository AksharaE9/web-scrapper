import React from "react";
import { CheckCircle2, HelpCircle, XCircle } from "lucide-react";
import { cn } from "../../lib/cn";

interface DecisionTabsProps {
  activeTab: "accepted" | "review" | "rejected";
  onTabChange: (tab: "accepted" | "review" | "rejected") => void;
  counts: {
    accepted: number;
    review: number;
    rejected: number;
  };
}

export const DecisionTabs: React.FC<DecisionTabsProps> = ({
  activeTab,
  onTabChange,
  counts,
}) => {
  const tabs = [
    {
      id: "accepted" as const,
      label: "Accepted",
      count: counts.accepted,
      icon: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
      activeClasses: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
    },
    {
      id: "review" as const,
      label: "Review Needed",
      count: counts.review,
      icon: <HelpCircle className="w-4 h-4 text-amber-500" />,
      activeClasses: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30",
    },
    {
      id: "rejected" as const,
      label: "Vetoed / Rejected",
      count: counts.rejected,
      icon: <XCircle className="w-4 h-4 text-rose-500" />,
      activeClasses: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30",
    },
  ];

  return (
    <div className="flex items-center gap-2 border-b border-border-subtle pb-3">
      {tabs.map((t) => {
        const isActive = activeTab === t.id;
        return (
          <button
            key={t.id}
            type="button"
            data-testid={`tab-${t.id}`}
            onClick={() => onTabChange(t.id)}
            className={cn(
              "flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold border transition-all cursor-pointer",
              isActive
                ? t.activeClasses
                : "bg-surface-1 text-text-secondary border-border-subtle hover:bg-surface-2"
            )}
          >
            {t.icon}
            <span>{t.label}</span>
            <span
              data-testid={`tab-${t.id}-count`}
              className="font-mono text-[11px] px-1.5 py-0.2 rounded bg-surface-2 border border-border-subtle"
            >
              {t.count}
            </span>
          </button>
        );
      })}
    </div>
  );
};
