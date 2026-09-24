import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ReasonChip } from "../../components/ui/ReasonChip";

describe("ReasonChip", () => {
  it("renders label as text", () => {
    render(<ReasonChip label="category: religious_goods_store" type="positive" />);
    expect(screen.getByText("category: religious_goods_store")).toBeInTheDocument();
  });

  it("object-valued icon degrades and never throws", () => {
    render(
      <ReasonChip
        label="category match"
        icon={{ type: "check", label: "ok", icon: "x" } as any}
        type="positive"
      />
    );
    expect(screen.getByText("category match")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\[object Object\]/);
  });

  it("all types render an icon and text (never colour alone)", () => {
    const { rerender } = render(<ReasonChip type="positive" label="Positive signal" />);
    expect(screen.getByText("Positive signal")).toBeInTheDocument();
    expect(document.querySelector("svg")).toBeInTheDocument();

    rerender(<ReasonChip type="negative" label="Negative signal" />);
    expect(screen.getByText("Negative signal")).toBeInTheDocument();
    expect(document.querySelector("svg")).toBeInTheDocument();

    rerender(<ReasonChip type="neutral" label="Neutral signal" />);
    expect(screen.getByText("Neutral signal")).toBeInTheDocument();
    expect(document.querySelector("svg")).toBeInTheDocument();
  });

  it("handles null or undefined label gracefully", () => {
    render(<ReasonChip label={null as any} type="positive" />);
    expect(screen.getByText("signal")).toBeInTheDocument();
  });
});
