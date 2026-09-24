import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DecisionTabs } from "./DecisionTabs";

describe("DecisionTabs", () => {
  it("renders counts for each tab", () => {
    render(
      <DecisionTabs
        activeTab="accepted"
        onTabChange={vi.fn()}
        counts={{ accepted: 19, review: 4, rejected: 61 }}
      />
    );

    expect(screen.getByTestId("tab-accepted-count")).toHaveTextContent("19");
    expect(screen.getByTestId("tab-review-count")).toHaveTextContent("4");
    expect(screen.getByTestId("tab-rejected-count")).toHaveTextContent("61");
  });

  it("clicking a tab calls onTabChange with that tab id", () => {
    const onTabChange = vi.fn();
    render(
      <DecisionTabs
        activeTab="accepted"
        onTabChange={onTabChange}
        counts={{ accepted: 19, review: 4, rejected: 61 }}
      />
    );

    fireEvent.click(screen.getByTestId("tab-review"));
    expect(onTabChange).toHaveBeenCalledWith("review");

    fireEvent.click(screen.getByTestId("tab-rejected"));
    expect(onTabChange).toHaveBeenCalledWith("rejected");
  });

  it("the three tabs are disjoint and have distinct labels", () => {
    render(
      <DecisionTabs
        activeTab="accepted"
        onTabChange={vi.fn()}
        counts={{ accepted: 10, review: 5, rejected: 2 }}
      />
    );

    expect(screen.getByRole("button", { name: /accepted/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /review needed/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /vetoed \/ rejected/i })).toBeInTheDocument();
  });
});
