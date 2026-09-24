import { screen, waitFor } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RunsPage } from "./RunsPage";
import { renderWithProviders } from "../../test/utils";

describe("RunsPage", () => {
  it("renders list of historical runs", async () => {
    renderWithProviders(<RunsPage />);

    await waitFor(() => {
      expect(screen.getByText(/HSR Layout/i)).toBeInTheDocument();
    });

    expect(screen.getByText("19")).toBeInTheDocument();
  });
});
