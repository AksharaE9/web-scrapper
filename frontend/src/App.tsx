import React, { useState } from "react";
import { Header } from "./components/Header";
import { LeftRailNav, TabType } from "./components/LeftRailNav";
import { ScrapeSection } from "./features/scrape/ScrapeSection";
import { RunsSection } from "./features/runs/RunsSection";
import { QualitySection } from "./features/quality/QualitySection";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>("scrape");
  const [darkMode, setDarkMode] = useState<boolean>(true);
  const [latestRunId, setLatestRunId] = useState<string | null>(null);
  const [runningCount, setRunningCount] = useState<number>(0);

  const handleRunStarted = (runId: string) => {
    setLatestRunId(runId);
    setRunningCount((prev: number) => prev + 1);
  };

  return (
    <div className={`min-h-screen flex flex-col ${darkMode ? "dark bg-slate-950 text-slate-100" : "bg-slate-50 text-slate-900"}`}>
      {/* Top Header with live health dots */}
      <Header darkMode={darkMode} setDarkMode={setDarkMode} />

      {/* Main Workspace Layout with Three-Section Left Rail */}
      <div className="flex-1 flex overflow-hidden">
        <LeftRailNav
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          runningCount={runningCount}
        />

        {/* Content Viewport */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-gradient-to-b from-slate-950 via-slate-900/30 to-slate-950">
          {activeTab === "scrape" && (
            <ScrapeSection onRunStarted={handleRunStarted} />
          )}
          {activeTab === "runs" && (
            <RunsSection initialRunId={latestRunId} />
          )}
          {activeTab === "quality" && (
            <QualitySection />
          )}
        </main>
      </div>
    </div>
  );
};

export default App;

