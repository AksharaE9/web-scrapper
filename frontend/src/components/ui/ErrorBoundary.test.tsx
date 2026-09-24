import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { SectionErrorBoundary, RowErrorBoundary } from "./ErrorBoundary";

describe("ErrorBoundary components", () => {
  it("renders SectionErrorBoundary children when normal", () => {
    render(
      <SectionErrorBoundary context="test-section">
        <div>Section Content</div>
      </SectionErrorBoundary>
    );
    expect(screen.getByText("Section Content")).toBeInTheDocument();
  });

  it("renders RowErrorBoundary normal lead row", () => {
    const lead = {
      id: "lead-1",
      canonical_name: "Sri Lakshmi Pooja Stores",
      locality: "HSR Layout",
      phones_e164: ["+918041234567"],
    };

    render(
      <RowErrorBoundary lead={lead}>
        <div data-testid="lead-row">Normal Row</div>
      </RowErrorBoundary>
    );
    expect(screen.getByText("Normal Row")).toBeInTheDocument();
  });
});
