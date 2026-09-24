import React from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from "recharts";

interface YieldFunnelChartProps {
  rawIngested: number;
  relevancePassed: number;
  resolvedEntities: number;
  verifiedLeads: number;
}

export const YieldFunnelChart: React.FC<YieldFunnelChartProps> = ({
  rawIngested,
  relevancePassed,
  resolvedEntities,
  verifiedLeads,
}) => {
  const maxVal = Math.max(1, rawIngested);
  const data = [
    { stage: "Ingested", count: rawIngested, color: "#3b82f6", pct: "100%" },
    { stage: "Relevance (R4)", count: relevancePassed, color: "#8b5cf6", pct: `${Math.round((relevancePassed / maxVal) * 100)}%` },
    { stage: "Resolved (ER)", count: resolvedEntities, color: "#06b6d4", pct: `${Math.round((resolvedEntities / maxVal) * 100)}%` },
    { stage: "Accepted Leads", count: verifiedLeads, color: "#10b981", pct: `${Math.round((verifiedLeads / maxVal) * 100)}%` },
  ];

  return (
    <div className="p-4 rounded-lg border border-border-subtle bg-surface-1 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
          Pipeline Ingestion Yield Funnel
        </div>
        <div className="text-xs font-mono text-text-muted">
          Yield: <span className="font-bold text-emerald-500">{((verifiedLeads / maxVal) * 100).toFixed(1)}%</span>
        </div>
      </div>

      <div className="h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <XAxis dataKey="stage" stroke="#8492a6" fontSize={11} />
            <YAxis stroke="#8492a6" fontSize={11} fontStyle="mono" allowDecimals={false} />
            <Tooltip
              cursor={{ fill: "rgba(255, 255, 255, 0.05)" }}
              contentStyle={{
                backgroundColor: "#161922",
                borderColor: "#3f475c",
                borderRadius: "8px",
                fontSize: "12px",
                fontFamily: "monospace",
                color: "#f8fafc",
              }}
              formatter={(value: any, _name: any, item: any) => [
                `${Number(value).toLocaleString()} items (${item.payload.pct})`,
                "Count",
              ]}
            />
            <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={36}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Funnel Stage Summary */}
      <div className="grid grid-cols-4 gap-1 pt-2 border-t border-border-subtle text-center text-xs">
        {data.map((d) => (
          <div key={d.stage} className="flex flex-col items-center">
            <div className="text-[10px] text-text-muted truncate max-w-[80px]" title={d.stage}>
              {d.stage}
            </div>
            <div className="font-bold font-mono text-text-primary text-[11px] mt-0.5">
              {d.count.toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
