import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { StatTile } from "./StatTile";
import { EmptyState, ErrorState, Skeleton } from "./EmptyState";
import { Users } from "lucide-react";

describe("UI Components", () => {
  it("renders StatTile with label and value", () => {
    render(<StatTile label="Total Leads" value={42} subtext="19 accepted" icon={<Users data-testid="icon" />} />);
    expect(screen.getByText("Total Leads")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("19 accepted")).toBeInTheDocument();
    expect(screen.getByTestId("icon")).toBeInTheDocument();
  });

  it("renders EmptyState and handles action", async () => {
    const user = userEvent.setup();
    const handleAction = vi.fn();
    render(<EmptyState title="No Records" description="Try refining your query." actionLabel="Retry Action" onAction={handleAction} />);
    expect(screen.getByText("No Records")).toBeInTheDocument();
    expect(screen.getByText("Try refining your query.")).toBeInTheDocument();
    const btn = screen.getByRole("button", { name: /retry action/i });
    expect(btn).toBeInTheDocument();
    await user.click(btn);
    expect(handleAction).toHaveBeenCalled();
  });

  it("renders ErrorState and Skeleton", () => {
    render(<ErrorState title="Failed" error="Network error" onRetry={() => {}} />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();

    const { container } = render(<Skeleton className="w-10 h-10" />);
    expect(container.firstChild).toHaveClass("animate-pulse");
  });
});
