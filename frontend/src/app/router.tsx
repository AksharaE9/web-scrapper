import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { ScrapePage } from "../features/scrape/ScrapePage";
import { RunsPage } from "../features/runs/RunsPage";
import { RunDetailPage } from "../features/runs/RunDetailPage";
import { LiveRunPage } from "../features/runs/LiveRunPage";
import { QualityPage } from "../features/quality/QualityPage";
import { RouteErrorBoundary } from "../components/ui/ErrorBoundary";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteErrorBoundary context="RootShell" />,
    children: [
      {
        index: true,
        element: <Navigate to="/scrape" replace />,
      },
      {
        path: "scrape",
        element: <ScrapePage />,
        errorElement: <RouteErrorBoundary context="ScrapePage" />,
      },
      {
        path: "runs",
        element: <RunsPage />,
        errorElement: <RouteErrorBoundary context="RunsPage" />,
      },
      {
        path: "runs/:runId",
        element: <RunDetailPage />,
        errorElement: <RouteErrorBoundary context="RunDetailPage" />,
      },
      {
        path: "runs/:runId/live",
        element: <LiveRunPage />,
        errorElement: <RouteErrorBoundary context="LiveRunPage" />,
      },
      {
        path: "quality",
        element: <QualityPage />,
        errorElement: <RouteErrorBoundary context="QualityPage" />,
      },
      {
        path: "*",
        element: <Navigate to="/scrape" replace />,
      },
    ],
  },
]);
