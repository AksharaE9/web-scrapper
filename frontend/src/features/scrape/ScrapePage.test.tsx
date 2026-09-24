import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { ScrapePage } from "./ScrapePage";
import { renderWithProviders } from "../../test/utils";
import { useScrapeDraft } from "../../stores/useScrapeDraft";

describe("ScrapePage", () => {
  it("renders form inputs and launch button with active state when form is complete", async () => {
    // Default mock store has locality='Whitefield' and keywords=['pooja store']
    useScrapeDraft.setState({
      location: { locality: "Whitefield", city: "Bengaluru", state: "Karnataka", country: "India" },
      keywords: ["pooja store"],
      maxResults: 100,
    });

    renderWithProviders(<ScrapePage />);

    expect(screen.getByLabelText(/locality/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^city/i)).toBeInTheDocument();
    expect(screen.getByTestId("max-results")).toBeInTheDocument();

    const launchBtn = screen.getByRole("button", { name: /launch discovery/i });
    expect(launchBtn).toBeInTheDocument();
    expect(launchBtn).not.toBeDisabled();
    expect(launchBtn).toHaveClass("cursor-pointer");
  });

  it("disables and styles launch button as disabled when keywords are empty", async () => {
    useScrapeDraft.setState({
      location: { locality: "Whitefield", city: "Bengaluru", state: "Karnataka", country: "India" },
      keywords: [],
    });

    renderWithProviders(<ScrapePage />);

    const launchBtn = screen.getByRole("button", { name: /launch discovery/i });
    expect(launchBtn).toBeDisabled();
    expect(launchBtn).toHaveAttribute("aria-disabled", "true");
    expect(launchBtn).toHaveClass("cursor-not-allowed");
    expect(screen.getByText(/add at least one keyword/i)).toBeInTheDocument();
  });
});
