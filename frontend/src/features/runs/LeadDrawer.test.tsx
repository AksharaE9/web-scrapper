import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { LeadDrawer } from "./LeadDrawer";
import { GOLDEN_LEADS } from "../../test/fixtures/goldenRun";
import { renderWithProviders } from "../../test/utils";
import { Lead } from "../../types";

describe("LeadDrawer", () => {
  it("renders lead details and provenance list", () => {
    const lead = {
      ...GOLDEN_LEADS.items[0],
      id: GOLDEN_LEADS.items[0].business_id,
      field_provenance: [
        {
          field_name: "phone",
          source: "overture",
          confidence: 0.95,
          timestamp: "2026-09-23T05:00:00Z",
        },
      ],
    };

    renderWithProviders(<LeadDrawer lead={lead as unknown as Lead} runId="run-123" onClose={() => {}} />);

    expect(screen.getByTestId("lead-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("provenance-list")).toBeInTheDocument();
  });

  it("calls onClose when escape or close button is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const lead = { ...GOLDEN_LEADS.items[0], id: GOLDEN_LEADS.items[0].business_id };

    renderWithProviders(<LeadDrawer lead={lead as unknown as Lead} runId="run-123" onClose={onClose} />);

    const closeBtn = screen.getByRole("button", { name: "" }); // icon button
    await user.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });
});
