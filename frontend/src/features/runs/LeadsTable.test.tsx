import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { LeadsTable } from "./LeadsTable";
import { GOLDEN_LEADS } from "../../test/fixtures/goldenRun";
import { renderWithProviders } from "../../test/utils";
import { Lead } from "../../types";

describe("LeadsTable", () => {
  it("renders every lead including the hostile row", () => {
    renderWithProviders(<LeadsTable leads={GOLDEN_LEADS.items as unknown as Lead[]} />);
    expect(screen.getByText("Sri Lakshmi Pooja Stores")).toBeInTheDocument();
    expect(screen.getByText("Vinayaka Agarbatti Mart")).toBeInTheDocument();
    // the row whose reasons contain an object-valued icon and a malformed entry
    expect(screen.getByText("Ganesh Puja Bhandar")).toBeInTheDocument();
  });

  it("never renders an object as a child", () => {
    renderWithProviders(<LeadsTable leads={GOLDEN_LEADS.items as unknown as Lead[]} />);
    expect(document.body.textContent).not.toMatch(/\[object Object\]/);
    // the setup.ts console guard fails the test on any React error
  });

  it("row count matches the data", () => {
    renderWithProviders(<LeadsTable leads={GOLDEN_LEADS.items as unknown as Lead[]} />);
    expect(screen.getAllByTestId("lead-row")).toHaveLength(GOLDEN_LEADS.items.length);
  });

  it("renders name and phone even when enrichment fields are null", () => {
    renderWithProviders(
      <LeadsTable
        leads={[
          {
            ...GOLDEN_LEADS.items[0],
            emails: null,
            website_domain: null,
            relevance_reasons: null,
            tier: null,
          } as any,
        ]}
      />
    );
    expect(screen.getByText("Sri Lakshmi Pooja Stores")).toBeInTheDocument();
    expect(screen.getByText(/\+918041234567/)).toBeInTheDocument();
  });

  it("one broken row does not hide the others", () => {
    const rows = [
      GOLDEN_LEADS.items[0],
      { business_id: "x" } as any,
      GOLDEN_LEADS.items[1],
    ];
    renderWithProviders(<LeadsTable leads={rows as unknown as Lead[]} />);
    expect(screen.getByText("Sri Lakshmi Pooja Stores")).toBeInTheDocument();
    expect(screen.getByText("Vinayaka Agarbatti Mart")).toBeInTheDocument();
  });

  it("handles row clicking", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderWithProviders(<LeadsTable leads={GOLDEN_LEADS.items as unknown as Lead[]} onSelectLead={onSelect} />);

    const row = screen.getByText("Vinayaka Agarbatti Mart");
    await user.click(row);
    expect(onSelect).toHaveBeenCalledWith(GOLDEN_LEADS.items[1]);
  });
});
