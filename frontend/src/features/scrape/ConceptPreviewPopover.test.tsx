import { screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ConceptPreviewPopover } from "./ConceptPreviewPopover";
import { renderWithProviders } from "../../test/utils";

describe("ConceptPreviewPopover", () => {
  it("renders preview popover content", () => {
    renderWithProviders(<ConceptPreviewPopover keyword="pooja store" />);
    expect(screen.getByText(/Loading concept card/i)).toBeInTheDocument();
  });
});
