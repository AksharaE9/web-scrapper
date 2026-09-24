import React from "react";
import { Outlet } from "react-router-dom";
import { Header } from "./Header";
import { LeftRailNav } from "./LeftRailNav";
import { RunStatusBar } from "./RunStatusBar";

export const AppShell: React.FC = () => {
  return (
    <div className="h-screen flex flex-col overflow-hidden bg-surface-base text-text-primary">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        <LeftRailNav />
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 bg-surface-base">
          <Outlet />
        </main>
      </div>
      <RunStatusBar />
    </div>
  );
};
