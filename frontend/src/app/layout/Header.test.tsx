import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { Header } from "./Header";
import { renderWithProviders } from "../../test/utils";

describe("Header", () => {
  it("renders branding and controls", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Header />);

    expect(screen.getByText("LeadCore Zero")).toBeInTheDocument();
    expect(screen.getByText("v3.0 Engine")).toBeInTheDocument();

    const healthBtn = screen.getByTitle("Backend Health Status");
    expect(healthBtn).toBeInTheDocument();

    await user.click(healthBtn);
    expect(screen.getByText("SYSTEM HEALTH")).toBeInTheDocument();
  });
});
