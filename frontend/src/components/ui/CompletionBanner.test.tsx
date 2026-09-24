import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CompletionBanner } from "./CompletionBanner";

describe("CompletionBanner", () => {
  it("renders target_met notification properly", () => {
    render(
      <CompletionBanner
        reason="target_met"
        acceptedCount={30}
        targetCount={30}
      />
    );
    expect(screen.getByText(/30 of 30 leads found/i)).toBeInTheDocument();
  });

  it("renders no_new_leads with already_known count and actions", () => {
    const handleViewExisting = vi.fn();
    render(
      <CompletionBanner
        reason="no_new_leads"
        acceptedCount={0}
        targetCount={30}
        details={{ already_known: 41 }}
        locality="HSR Layout"
        onViewExisting={handleViewExisting}
      />
    );
    expect(screen.getByText(/0 of 30 found — 41 matches were already in your database from earlier runs/i)).toBeInTheDocument();
    const btn = screen.getByRole("button", { name: /View Existing \(41\)/i });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(handleViewExisting).toHaveBeenCalled();
  });

  it("renders region_exhausted with genuine exhaustion explanation", () => {
    render(
      <CompletionBanner
        reason="region_exhausted"
        acceptedCount={23}
        targetCount={30}
        details={{ rungs_tried: [{}, {}], categories_queried: 47 }}
        locality="HSR Layout"
      />
    );
    expect(screen.getByTestId("exhaustion-banner")).toBeInTheDocument();
    expect(screen.getByText(/23 of 30 found — this area is genuinely exhausted/i)).toBeInTheDocument();
  });

  it("renders budget_exhausted notification", () => {
    render(
      <CompletionBanner
        reason="budget_exhausted"
        acceptedCount={18}
        targetCount={30}
        details={{ limit: "time limit" }}
      />
    );
    expect(screen.getByText(/18 of 30 found — the run hit its time limit before finishing/i)).toBeInTheDocument();
  });

  it("renders partial_sources notification", () => {
    render(
      <CompletionBanner
        reason="partial_sources"
        acceptedCount={15}
        targetCount={30}
        details={{ failed: ["OpenStreetMap"] }}
      />
    );
    expect(screen.getByText(/15 of 30 found — OpenStreetMap was unavailable, so results are incomplete/i)).toBeInTheDocument();
  });

  it("renders low_relevance precision collapse explanation", () => {
    render(
      <CompletionBanner
        reason="low_relevance"
        acceptedCount={23}
        targetCount={30}
        details={{ candidates: 612 }}
        keyword="pooja store"
      />
    );
    expect(screen.getByText(/23 of 30 found — 612 candidates were checked and 589 didn't match 'pooja store'/i)).toBeInTheDocument();
  });

  it("can be dismissed by clicking the dismiss button", () => {
    render(
      <CompletionBanner
        reason="budget_exhausted"
        acceptedCount={10}
        targetCount={30}
      />
    );
    expect(screen.getByTestId("completion-banner-budget-exhausted")).toBeInTheDocument();
    const dismissBtn = screen.getByTitle(/Dismiss notification/i);
    fireEvent.click(dismissBtn);
    expect(screen.queryByTestId("completion-banner-budget-exhausted")).not.toBeInTheDocument();
  });
});
