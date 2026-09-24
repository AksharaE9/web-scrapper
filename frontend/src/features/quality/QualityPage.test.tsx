import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { QualityPage } from "./QualityPage";
import { MetricTile } from "./MetricTile";
import { renderWithProviders } from "../../test/utils";

describe("QualityPage & MetricTile", () => {
  it("renders Quality page with title and metric cards", () => {
    renderWithProviders(<QualityPage />);
    expect(screen.getByText(/Data Quality & Benchmark Evaluation/i)).toBeInTheDocument();
  });

  it("shows 'Label N more' when n < 30", () => {
    render(
      <MetricTile
        label="Test Metric"
        value={0.85}
        kind="measured"
        sampleSize={12}
        requiredLabels={30}
      />
    );

    expect(screen.getByText(/Label 18 more to unlock/i)).toBeInTheDocument();
    expect(screen.getByText("INSUFFICIENT LABELS")).toBeInTheDocument();
    expect(screen.queryByText("MEASURED")).not.toBeInTheDocument();
  });

  it("an estimate can never carry a Measured badge", () => {
    render(
      <MetricTile
        label="Estimated Metric"
        value={0.75}
        kind="proxy"
        sampleSize={50}
      />
    );

    expect(screen.getByText("ESTIMATE")).toBeInTheDocument();
    expect(screen.queryByText("MEASURED")).not.toBeInTheDocument();
  });
});
