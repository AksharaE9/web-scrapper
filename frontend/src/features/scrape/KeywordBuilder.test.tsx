import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { KeywordBuilder } from "./KeywordBuilder";
import { useScrapeDraft } from "../../stores/useScrapeDraft";
import { renderWithProviders } from "../../test/utils";

describe("KeywordBuilder", () => {
  it("adds, removes, and prevents duplicate keywords without key collision warnings", async () => {
    const user = userEvent.setup();
    useScrapeDraft.getState().setKeywords(["pooja store"]);

    renderWithProviders(<KeywordBuilder />);

    const input = screen.getByPlaceholderText(/add.*keyword/i);
    await user.type(input, "agarbatti{enter}");

    expect(useScrapeDraft.getState().keywords).toContain("agarbatti");
    expect(screen.getAllByTestId("keyword-chip")).toHaveLength(2);
  });
});
