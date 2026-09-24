import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { Routes, Route } from "react-router-dom";
import { RunDetailPage } from "./RunDetailPage";
import { renderWithProviders } from "../../test/utils";
import { GOLDEN_RUN } from "../../test/fixtures/goldenRun";

describe("RunDetailPage", () => {
  it("renders run details with status and tab counts", async () => {
    renderWithProviders(
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>,
      {
        route: `/runs/${GOLDEN_RUN.id}?tab=accepted`,
      }
    );

    await waitFor(() => {
      expect(screen.getByTestId("run-status")).toBeInTheDocument();
    });

    expect(screen.getByTestId("tab-accepted-count")).toBeInTheDocument();
  });

  it("exhaustion banner renders when region is exhausted", async () => {
    renderWithProviders(
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>,
      {
        route: `/runs/${GOLDEN_RUN.id}?tab=accepted`,
      }
    );

    await waitFor(() => {
      expect(screen.getByTestId("exhaustion-banner")).toBeInTheDocument();
    });
  });

  it("shows error state when run is not found", async () => {
    renderWithProviders(
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>,
      {
        route: "/runs/00000000-0000-0000-0000-000000000000",
      }
    );

    await waitFor(() => {
      expect(screen.getByText(/Run Not Found/i)).toBeInTheDocument();
    });
  });

  it("handles tab changes and export button", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>,
      {
        route: `/runs/${GOLDEN_RUN.id}?tab=accepted`,
      }
    );

    await waitFor(() => {
      expect(screen.getByTestId("run-status")).toBeInTheDocument();
    });

    const reviewTab = screen.getByTestId("tab-review");
    await user.click(reviewTab);

    const exportBtn = screen.getByRole("button", { name: /csv/i });
    expect(exportBtn).toBeInTheDocument();
  });
});
