import { screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Route, Routes } from "react-router-dom";
import { LiveRunPage } from "./LiveRunPage";
import { renderWithProviders } from "../../test/utils";

describe("LiveRunPage", () => {
  it("renders LiveRunPanel with active runId param", () => {
    renderWithProviders(
      <Routes>
        <Route path="/runs/:runId/live" element={<LiveRunPage />} />
      </Routes>,
      { route: "/runs/11111111-1111-4111-8111-111111111111/live" }
    );
    expect(screen.getByText("Lead Discovery Run")).toBeInTheDocument();
  });
});
