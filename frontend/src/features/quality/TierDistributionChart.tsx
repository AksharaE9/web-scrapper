import React from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from "recharts";

interface TierDistributionChartProps {
  verified: number;
  likely: number;
  unverified: number;
}

export const TierDistributionChart: React.FC<TierDistributionChartProps> = ({
  verified,
  likely,
  unverified,
}) => {
  const total = verified + likely + unverified;
  const data = [
    { tier: "Verified", count: verified, color: "#10b981", pct: total > 0 ? Math.round((verified / total) * 100) : 0 },
    { tier: "Likely", count: likely, color: "#f59e0b", pct: total > 0 ? Math.round((likely / total) * 100) : 0 },
    { tier: "Unverified", count: unverified, color: "#64748b", pct: total > 0 ? Math.round((unverified / total) * 100) : 0 },
  ];

  return (
    <div className="p-4 rounded-lg border border-border-subtle bg-surface-1 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
          Confidence Tier Distribution
        </div>
        <div className="text-xs font-mono text-text-muted">
          Total: <span className="font-bold text-text-primary">{total}</span> leads
        </div>
      </div>

      <div className="h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
            <XAxis type="number" stroke="#8492a6" fontSize={11} fontStyle="mono" allowDecimals={false} />
            <YAxis dataKey="tier" type="category" stroke="#8492a6" fontSize={11} width={80} />
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
                `${value} leads (${item.payload.pct}%)`,
                "Count",
              ]}
            />
            <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={20}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Mini Legend with exact counts */}
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-border-subtle text-center text-xs">
        {data.map((d) => (
          <div key={d.tier} className="flex flex-col items-center">
            <div className="flex items-center gap-1 text-[11px] text-text-muted">
              <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: d.color }} />
              {d.tier}
            </div>
            <div className="font-bold font-mono text-text-primary mt-0.5">
              {d.count} <span className="text-[10px] text-text-muted font-normal">({d.pct}%)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
