import { screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RunCard } from "./RunCard";
import { GOLDEN_RUN } from "../../test/fixtures/goldenRun";
import { renderWithProviders } from "../../test/utils";

describe("RunCard", () => {
  it("renders retry button when status: 'failed' and retryable: true", () => {
    renderWithProviders(<RunCard run={{ ...GOLDEN_RUN, status: "failed", error: "Connection lost", retryable: true } as any} />);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders 'Can't re-run' badge when status: 'failed' and retryable: false", () => {
    renderWithProviders(<RunCard run={{ ...GOLDEN_RUN, status: "failed", error: "Corrupt row", retryable: false } as any} />);
    expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
    expect(screen.getByText("Can't re-run")).toBeInTheDocument();
  });

  it("renders completion reason banner and lead counts for region_exhausted", () => {
    renderWithProviders(
      <RunCard run={{ ...GOLDEN_RUN, completion_reason: "region_exhausted", stats: { ...GOLDEN_RUN.stats, resolved_entity_count: 19 } } as any} />
    );
    expect(screen.getByTestId("exhaustion-badge")).toHaveTextContent("exhausted");
    expect(screen.getByText("19")).toBeInTheDocument();
  });

  it("displays human readable sentence instead of raw stacktrace on failure", () => {
    renderWithProviders(
      <RunCard
        run={
          {
            ...GOLDEN_RUN,
            status: "failed",
            error: "Traceback (most recent call last):\n  File 'worker.py', line 45\nValueError: database offline",
          } as any
        }
      />
    );
    expect(screen.getByText(/database offline/i)).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/i)).not.toBeInTheDocument();
  });
});
