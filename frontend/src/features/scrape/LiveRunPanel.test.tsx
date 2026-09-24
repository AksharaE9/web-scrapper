import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { LiveRunPanel } from "./LiveRunPanel";
import { renderWithProviders } from "../../test/utils";

describe("LiveRunPanel", () => {
  it("renders live run panel header and controls", async () => {
    renderWithProviders(<LiveRunPanel runId="11111111-1111-4111-8111-111111111111" />);

    await waitFor(() => {
      expect(screen.getByText("pooja store")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /edit & re-run/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open run workspace/i })).toBeInTheDocument();
  });

  it("handles edit and rerun interaction", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LiveRunPanel runId="11111111-1111-4111-8111-111111111111" />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /edit & re-run/i })).toBeInTheDocument();
    });

    const editBtn = screen.getByRole("button", { name: /edit & re-run/i });
    await user.click(editBtn);
  });
});
