import { screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RunOptions } from "./RunOptions";
import { useScrapeDraft } from "../../stores/useScrapeDraft";
import { renderWithProviders } from "../../test/utils";

describe("RunOptions", () => {
  it("renders target results input with data-testid max-results", () => {
    useScrapeDraft.getState().setMaxResults(30);

    renderWithProviders(<RunOptions />);

    const input = screen.getByTestId("max-results");
    expect(input).toHaveValue(30);
  });

  it("renders stub sources as disabled checkboxes", () => {
    renderWithProviders(<RunOptions />);

    const wikidataCheckbox = screen.getByTestId("source-wikidata");
    expect(wikidataCheckbox).toBeDisabled();

    const alltheplacesCheckbox = screen.getByTestId("source-alltheplaces");
    expect(alltheplacesCheckbox).toBeDisabled();
  });

  it("updates options when values change", () => {
    renderWithProviders(<RunOptions />);

    const input = screen.getByTestId("max-results");
    fireEvent.change(input, { target: { value: "50" } });

    expect(useScrapeDraft.getState().maxResults).toBe(50);
  });
});
