import React from "react";
import { useParams, useNavigate, Navigate } from "react-router-dom";
import { LiveRunPanel } from "../scrape/LiveRunPanel";

export const LiveRunPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  if (!runId) {
    return <Navigate to="/scrape" replace />;
  }

  return (
    <div className="max-w-6xl mx-auto pb-16">
      <LiveRunPanel runId={runId} onNewRun={() => navigate("/scrape")} />
    </div>
  );
};
