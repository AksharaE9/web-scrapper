import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { LeftRailNav } from "./LeftRailNav";
import { RunStatusBar } from "./RunStatusBar";
import { AppShell } from "./AppShell";
import { renderWithProviders } from "../../test/utils";
import { useRunTracker } from "../../stores/useRunTracker";

describe("Layout Components", () => {
  it("renders LeftRailNav navigation items", () => {
    renderWithProviders(<LeftRailNav />);
    expect(screen.getByText("Scrape")).toBeInTheDocument();
    expect(screen.getByText("Runs")).toBeInTheDocument();
    expect(screen.getByText("Quality")).toBeInTheDocument();
  });

  it("renders RunStatusBar with active runs and handles clear", async () => {
    const user = userEvent.setup();
    useRunTracker.getState().trackRun("run-999", "pooja store", "Indiranagar");

    renderWithProviders(<RunStatusBar />);
    expect(screen.getByText(/pooja store · Indiranagar/i)).toBeInTheDocument();

    const clearBtn = screen.getByRole("button");
    await user.click(clearBtn);

    expect(useRunTracker.getState().activeRuns["run-999"]).toBeUndefined();
  });

  it("renders AppShell with header and nav", () => {
    renderWithProviders(<AppShell />);
    expect(screen.getByText("LeadCore Zero")).toBeInTheDocument();
  });
});
