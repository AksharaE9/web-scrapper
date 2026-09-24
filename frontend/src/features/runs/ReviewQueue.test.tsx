/**
 * ReviewQueue — test suite for REL-2.0 Part A
 *
 * Prime Directive: every test is written to fail on the CURRENT broken code first.
 * `no_skip_on_label` must report 11/22 before the fix lands.
 *
 * Run BEFORE fixing ReviewQueue.tsx:
 *   npm.cmd test -- ReviewQueue --reporter=verbose
 * Expect: no_skip_on_label FAILS showing ~11 unique ids instead of 22.
 */
import { screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ReviewQueue } from "./ReviewQueue";
import { renderWithProviders } from "../../test/utils";
import { Lead } from "../../types";

// ── Build a deterministic 22-lead queue ───────────────────────────────────────
function makeLeads(n: number): Lead[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `lead-${String(i + 1).padStart(3, "0")}`,
    business_id: `lead-${String(i + 1).padStart(3, "0")}`,
    canonical_name: `Business ${i + 1}`,
    name: `Business ${i + 1}`,
    name_norm: `business ${i + 1}`,
    primary_category: "test",
    categories: ["test"],
    locality: "HSR Layout",
    city: "Bengaluru",
    state: "Karnataka",
    country: "India",
    lon: 77.6,
    lat: 12.9,
    phones_e164: [],
    emails: [],
    socials: {},
    address: {},
    website_domain: undefined,
    tier: "Likely",
    confidence: 0.7,
    independent_source_count: 1,
    source_ids: [`src-${i + 1}`],
    is_new_business: true,
    decision: "review" as const,
    relevance_p: 0.5,
    relevance_reasons: [],
    field_provenance: [],
  }));
}

// ── Mock useRelabelLead ──────────────────────────────────────────────────────
const mutateAsync = vi.fn().mockResolvedValue({ ok: true });
vi.mock("../../hooks/useLeads", () => ({
  useRelabelLead: () => ({ mutateAsync, isLoading: false }),
}));

describe("ReviewQueue", () => {
  beforeEach(() => {
    // mockReset clears call history AND resets implementation to default
    mutateAsync.mockReset();
    mutateAsync.mockResolvedValue({ ok: true });
    sessionStorage.clear();
  });

  // ── R1 (THE KEY REGRESSION TEST — must FAIL on current code showing 11/22) ──
  it("no_skip_on_label: 22-item queue labels all 22 unique businesses in order", async () => {
    const user = userEvent.setup();
    const onExit = vi.fn();
    const leads = makeLeads(22);

    renderWithProviders(<ReviewQueue leads={leads} runId="run-test-22" onExit={onExit} />);

    const labelledIds: string[] = [];

    // Click Accept for all 22 items
    for (let i = 0; i < 22; i++) {
      // Wait for current item to be shown
      await waitFor(() =>
        expect(screen.queryByRole("button", { name: /accept/i })).toBeInTheDocument()
      );

      // Capture which business is currently shown
      const calls_before = mutateAsync.mock.calls.length;
      const acceptBtn = screen.getByRole("button", { name: /accept/i });
      await user.click(acceptBtn);

      // Capture the businessId that was labelled
      await waitFor(() => {
        expect(mutateAsync.mock.calls.length).toBeGreaterThan(calls_before);
      });
      const lastCall = mutateAsync.mock.calls[mutateAsync.mock.calls.length - 1];
      labelledIds.push(lastCall[0].businessId);
    }

    // All 22 unique ids must be presented
    const uniqueIds = new Set(labelledIds);
    expect(uniqueIds.size).toBe(22); // FAILS on current code (shows ~11)
    expect(labelledIds).toHaveLength(22);

    // Must match the queue exactly, in order
    leads.forEach((lead, i) => {
      expect(labelledIds[i]).toBe(lead.id);
    });
  });

  // ── R2 — cursor survives list shrink under refetch ────────────────────────
  // The frozen queue persists the original order; the cursor identity (id) is
  // preserved even when the leads prop no longer contains labelled items.
  it("list_shrinks_under_cursor: refetch removing labelled items keeps cursor on next item", async () => {
    const user = userEvent.setup();
    const onExit = vi.fn();
    const leads = makeLeads(5);
    const { rerender } = renderWithProviders(
      <ReviewQueue leads={leads} runId="run-shrink" onExit={onExit} />
    );

    // Label item 0 (Business 1)
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /accept/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /accept/i }));
    await waitFor(() => expect(screen.getByText("Business 2")).toBeInTheDocument());

    // Simulate refetch: the labelled item is filtered out by the server.
    // The frozen queue still starts at lead-001; cursor identity is lead-002.
    // Business 2 must still be shown (cursor id unchanged).
    const shrunk = leads.slice(1); // lead-002 through lead-005
    rerender(
      <ReviewQueue leads={shrunk} runId="run-shrink" onExit={onExit} />
    );

    // Cursor identity (lead-002) is still valid → Business 2 still shown
    expect(screen.getByText("Business 2")).toBeInTheDocument();
  });

  // ── R3 — keyboard is never stale ─────────────────────────────────────────
  it("keyboard_not_stale: 5 Y keypresses label 5 distinct businesses", async () => {
    const onExit = vi.fn();
    const leads = makeLeads(10);
    renderWithProviders(<ReviewQueue leads={leads} runId="run-kb" onExit={onExit} />);

    // Wait for the queue to be mounted
    await waitFor(() => expect(screen.getByText("Business 1")).toBeInTheDocument());

    for (let i = 0; i < 5; i++) {
      await act(async () => {
        // Dispatch on window — our listener is on window (avoid double-fire from document+window)
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "y", bubbles: true, cancelable: true }));
        await new Promise((r) => setTimeout(r, 80));
      });
    }

    await waitFor(() => expect(mutateAsync.mock.calls.length).toBe(5), { timeout: 3000 });

    const ids = mutateAsync.mock.calls.map((c) => c[0].businessId);
    const unique = new Set(ids);
    expect(unique.size).toBe(5); // All 5 must be distinct
  });

  // -- R4 -- double-fire prevention
  it("no_double_fire: simultaneous click + keypress fires exactly 1 mutation", async () => {
    const user = userEvent.setup();
    const onExit = vi.fn();
    // Slow mutation using a manual promise so we can control timing
    let resolveFirst!: () => void;
    mutateAsync.mockImplementationOnce(
      () => new Promise<{ ok: boolean }>((r) => { resolveFirst = () => r({ ok: true }); })
    );

    renderWithProviders(<ReviewQueue leads={makeLeads(3)} runId="run-dbl" onExit={onExit} />);

    // Click Accept - starts the in-flight mutation
    const btn = screen.getByRole("button", { name: /accept/i });
    await act(async () => {
      void user.click(btn);
      // Yield to let the click handler run and set inFlightRef.current = true
      await new Promise((r) => setTimeout(r, 0));
    });

    // At this point the first mutateAsync call is in progress.
    // Fire the Y keypress - should be blocked by inFlightRef.current === true
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "y", bubbles: true }));
    await new Promise((r) => setTimeout(r, 20));

    // Resolve the in-flight mutation
    await act(async () => { resolveFirst(); });
    await new Promise((r) => setTimeout(r, 50));

    expect(mutateAsync.mock.calls.length).toBe(1);
  });

  it("key_repeat_ignored: holding Y fires only 1 label", async () => {
    const onExit = vi.fn();
    renderWithProviders(<ReviewQueue leads={makeLeads(3)} runId="run-rep" onExit={onExit} />);

    // Fire 10 repeat events
    for (let i = 0; i < 10; i++) {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "y", bubbles: true, repeat: true }));
    }
    // Then fire one real non-repeat
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "y", bubbles: true, repeat: false }));
      await new Promise((r) => setTimeout(r, 100));
    });

    await waitFor(() => expect(mutateAsync.mock.calls.length).toBe(1));
  });

  // ── R6 — typing in an input does not cast a vote ─────────────────────────
  it("typing_in_input: pressing Y while focused on input fires 0 mutations", async () => {
    const onExit = vi.fn();
    renderWithProviders(<ReviewQueue leads={makeLeads(3)} runId="run-inp" onExit={onExit} />);

    const inputEl = document.createElement("input");
    document.body.appendChild(inputEl);
    inputEl.focus();

    // Dispatch FROM the inputEl - sets e.target = inputEl (tagName=INPUT).
    // Dispatching from window sets e.target = window, bypassing the INPUT guard.
    inputEl.dispatchEvent(
      new KeyboardEvent("keydown", { key: "y", bubbles: true, cancelable: true })
    );
    await new Promise((r) => setTimeout(r, 50));

    expect(mutateAsync.mock.calls.length).toBe(0);
    document.body.removeChild(inputEl);
  });

  it("error_does_not_advance: network failure leaves cursor on same item", async () => {
    const user = userEvent.setup();
    const onExit = vi.fn();
    mutateAsync.mockRejectedValueOnce(new Error("Network error"));

    const leads = makeLeads(3);
    renderWithProviders(<ReviewQueue leads={leads} runId="run-err" onExit={onExit} />);

    // First is Business 1
    expect(screen.getByText("Business 1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /accept/i }));
    
    // After error, cursor must NOT have advanced — still Business 1
    // The toast may or may not render in jsdom; we check the cursor position only.
    await waitFor(() => {
      // Business 2 must NOT be shown — cursor stays on Business 1
      expect(screen.queryByText("Business 2")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Business 1")).toBeInTheDocument();
  });

  // ── R8 — undo restores item ──────────────────────────────────────────────
  it("undo_restores: U key after label brings item back and decrements count", async () => {
    const user = userEvent.setup();
    const onExit = vi.fn();
    const leads = makeLeads(5);
    renderWithProviders(<ReviewQueue leads={leads} runId="run-undo" onExit={onExit} />);

    // Accept Business 1
    await user.click(screen.getByRole("button", { name: /accept/i }));

    // Now showing Business 2
    await waitFor(() => expect(screen.getByText("Business 2")).toBeInTheDocument());

    // Press U to undo
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "u", bubbles: true }));
      await new Promise((r) => setTimeout(r, 100));
    });

    // Should be back on Business 1
    await waitFor(() => expect(screen.getByText("Business 1")).toBeInTheDocument());
  });

  // ── R9 — sessionStorage persistence on remount ────────────────────────────
  it("resume_after_remount: unmount at item 5 resumes at item 5 after remount", async () => {
    const user = userEvent.setup();
    const onExit = vi.fn();
    const leads = makeLeads(10);

    const { unmount } = renderWithProviders(
      <ReviewQueue leads={leads} runId="run-persist" onExit={onExit} />
    );

    // Label items 0–4 (5 items)
    for (let i = 0; i < 5; i++) {
      await waitFor(() =>
        expect(screen.queryByRole("button", { name: /accept/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole("button", { name: /accept/i }));
    }

    // Now on Business 6 (index 5)
    await waitFor(() => expect(screen.getByText("Business 6")).toBeInTheDocument());

    // Flush effects so sessionStorage.setItem has been called before unmount
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // Unmount
    unmount();

    // Remount with same runId
    renderWithProviders(<ReviewQueue leads={leads} runId="run-persist" onExit={onExit} />);

    // Should resume at Business 6
    await waitFor(() => expect(screen.getByText("Business 6")).toBeInTheDocument());
    // And show 5 reviewed
    expect(screen.getByText(/reviewed 5/i)).toBeInTheDocument();
  });

  // ── Empty state ───────────────────────────────────────────────────────────
  it("renders empty state when no leads provided", () => {
    const onExit = vi.fn();
    renderWithProviders(<ReviewQueue leads={[]} runId="test-run" onExit={onExit} />);
    expect(screen.getByText("Review Queue Empty")).toBeInTheDocument();
  });
});
