import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuditEntry } from "@/lib/api/audit.server";
import { renderWithQuery } from "@/test/render";
import { AuditPage } from "./audit-page";

const mocks = vi.hoisted(() => ({
  listAuditEntries: vi.fn(),
  verifyAuditChain: vi.fn(),
  runIntegrityReport: vi.fn(),
  runRetention: vi.fn(),
}));

vi.mock("@/lib/api/audit.server", () => ({
  listAuditEntries: mocks.listAuditEntries,
  verifyAuditChain: mocks.verifyAuditChain,
  runIntegrityReport: mocks.runIntegrityReport,
  runRetention: mocks.runRetention,
}));

function entry(overrides: Partial<AuditEntry> = {}): AuditEntry {
  return {
    seq: 1,
    event_type: "test_event",
    entity_reference: null,
    session_id: null,
    entry_hash: "a".repeat(64),
    previous_hash: "0".repeat(64),
    created_at: "2026-01-02T03:04:05Z",
    payload: {},
    ...overrides,
  };
}

beforeEach(() => {
  mocks.listAuditEntries.mockResolvedValue({
    entries: [],
    has_more: false,
    next_before_seq: null,
  });
  mocks.verifyAuditChain.mockResolvedValue({ intact: true, entries: 0 });
  mocks.runIntegrityReport.mockResolvedValue({
    ok: true,
    orphans: {},
    audit_chain_intact: true,
    audit_entries: 0,
  });
  mocks.runRetention.mockResolvedValue({
    cutoff: "2026-01-01T00:00:00+00:00",
    sessions_matched: 0,
    turns_anonymized: 0,
    dry_run: true,
  });
});

describe("audit ledger", () => {
  it("shows the loading skeleton while the first page is pending", () => {
    mocks.listAuditEntries.mockReturnValue(new Promise(() => {}));

    renderWithQuery(<AuditPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  it("shows the empty ledger state", async () => {
    renderWithQuery(<AuditPage />);

    expect(await screen.findByText("No audit entries")).toBeInTheDocument();
    expect(screen.getByText("Nothing has been recorded yet.")).toBeInTheDocument();
  });

  it("renders loaded rows newest-first", async () => {
    mocks.listAuditEntries.mockResolvedValue({
      entries: [entry({ seq: 501 }), entry({ seq: 500 }), entry({ seq: 499 })],
      has_more: false,
      next_before_seq: null,
    });

    renderWithQuery(<AuditPage />);

    await screen.findByText("501");
    const rows = screen.getAllByRole("row").slice(1);
    ["501", "500", "499"].forEach((seq, index) => {
      expect(within(rows[index]!).getByText(seq)).toBeInTheDocument();
    });
  });

  it("shows the fatal error and recovers when retry is pressed", async () => {
    mocks.listAuditEntries.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    expect(await screen.findByText("Could not load")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();

    mocks.listAuditEntries.mockResolvedValue({
      entries: [entry({ seq: 501 })],
      has_more: false,
      next_before_seq: null,
    });
    await user.click(screen.getByRole("button", { name: /try again/i }));

    expect(await screen.findByText("501")).toBeInTheDocument();
    expect(screen.queryByText("Could not load")).not.toBeInTheDocument();
  });

  it("starts an isolated query for an exact event filter", async () => {
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    await screen.findByText("No audit entries");

    await user.type(screen.getByPlaceholderText("Filter by event type"), "login");

    await waitFor(() => {
      expect(mocks.listAuditEntries).toHaveBeenLastCalledWith({
        data: { eventType: "login", beforeSeq: undefined },
      });
    });
  });

  it("fetches the next block with next_before_seq once the reader reaches the end", async () => {
    // One block of 6 fills two view pages (5 + 1); the second page is the end of what is loaded,
    // so arriving there is what pulls the next block in.
    mocks.listAuditEntries
      .mockResolvedValueOnce({
        entries: [500, 499, 498, 497, 496, 495].map((seq) => entry({ seq })),
        has_more: true,
        next_before_seq: 451,
      })
      .mockResolvedValue({ entries: [], has_more: false, next_before_seq: null });
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    await screen.findByText("500");
    await user.click(screen.getByRole("button", { name: "Next page" }));

    await waitFor(() => {
      expect(mocks.listAuditEntries).toHaveBeenLastCalledWith({
        data: { eventType: undefined, beforeSeq: 451 },
      });
    });
  });

  it("disables paging forward when the ledger is empty", async () => {
    renderWithQuery(<AuditPage />);

    await screen.findByText("No audit entries");

    // A single (empty) page means there is nowhere forward to go.
    expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument();
  });

  it("shows at most five entries per view, whatever the fetch block size", async () => {
    // A realistic block: the backend answers in 50s, the VIEW must still show five.
    mocks.listAuditEntries.mockResolvedValue({
      entries: Array.from({ length: 12 }, (_, index) => entry({ seq: 500 - index })),
      has_more: false,
      next_before_seq: null,
    });
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    await screen.findByText("500");
    // header row + five data rows — this is the regression the old block-per-view paging hid.
    expect(screen.getAllByRole("row")).toHaveLength(6);
    expect(screen.queryByText("495")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next page" }));

    await screen.findByText("495");
    expect(screen.getAllByRole("row")).toHaveLength(6);
    // The newer page is replaced, not appended: the table never grows.
    expect(screen.queryByText("500")).not.toBeInTheDocument();

    // Paging within a fetched block is pure slicing — no extra request.
    expect(mocks.listAuditEntries).toHaveBeenCalledTimes(1);
  });

  it("does not duplicate rows when a second block is appended", async () => {
    mocks.listAuditEntries
      .mockResolvedValueOnce({
        entries: [500, 499, 498, 497, 496, 495].map((seq) => entry({ seq })),
        has_more: true,
        next_before_seq: 494,
      })
      .mockResolvedValueOnce({
        entries: [494, 493].map((seq) => entry({ seq })),
        has_more: false,
        next_before_seq: null,
      });
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    await screen.findByText("500");
    await user.click(screen.getByRole("button", { name: "Next page" }));

    // Page 2 holds the tail of block one plus the whole of block two, each exactly once.
    await screen.findByText("494");
    for (const seq of ["495", "494", "493"]) {
      expect(screen.getAllByText(seq)).toHaveLength(1);
    }
    expect(screen.getAllByRole("row").length).toBeLessThanOrEqual(6);
  });

  it("hides link mismatch while the adjacent older row is not loaded", async () => {
    mocks.listAuditEntries.mockResolvedValue({
      entries: [entry({ seq: 500, previous_hash: "b".repeat(64), entry_hash: "a".repeat(64) })],
      has_more: false,
      next_before_seq: null,
    });

    renderWithQuery(<AuditPage />);

    await screen.findByText("500");
    expect(screen.queryByText("link mismatch")).not.toBeInTheDocument();
  });

  it("shows link mismatch only for the newer row of a broken link", async () => {
    mocks.listAuditEntries.mockResolvedValue({
      entries: [
        entry({ seq: 501, previous_hash: "b".repeat(64), entry_hash: "a".repeat(64) }),
        entry({ seq: 500, previous_hash: "a".repeat(64), entry_hash: "c".repeat(64) }),
      ],
      has_more: false,
      next_before_seq: null,
    });

    renderWithQuery(<AuditPage />);

    await screen.findByText("501");
    expect(screen.getByText("link mismatch")).toBeInTheDocument();

    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]!).getByText("link mismatch")).toBeInTheDocument();
    expect(within(rows[1]!).queryByText("link mismatch")).not.toBeInTheDocument();
  });
});

describe("chain verification", () => {
  it("is not run automatically", async () => {
    renderWithQuery(<AuditPage />);

    expect(
      await screen.findByText(/verification reads the whole ledger, so it runs only when you ask/i),
    ).toBeInTheDocument();
    expect(mocks.verifyAuditChain).not.toHaveBeenCalled();
  });

  it("shows the intact state when the chain verifies", async () => {
    mocks.verifyAuditChain.mockResolvedValue({ intact: true, entries: 12 });
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    await user.click(await screen.findByRole("button", { name: "Verify chain" }));

    expect(await screen.findByText("Chain intact")).toBeInTheDocument();
    expect(screen.getByText("12 entries")).toBeInTheDocument();
  });

  it("shows the broken state when the chain fails", async () => {
    mocks.verifyAuditChain.mockResolvedValue({ intact: false, entries: 12 });
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    await user.click(await screen.findByRole("button", { name: "Verify chain" }));

    expect(await screen.findByText(/chain broken/i)).toBeInTheDocument();
  });

  it("shows the error when the request fails", async () => {
    mocks.verifyAuditChain.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    await user.click(await screen.findByRole("button", { name: "Verify chain" }));

    expect(await screen.findByText(/could not reach the service/i)).toBeInTheDocument();
  });
});

describe("integrity verification", () => {
  it("is not run automatically", async () => {
    renderWithQuery(<AuditPage />);

    expect(await screen.findByText("Not run yet.")).toBeInTheDocument();
    expect(mocks.runIntegrityReport).not.toHaveBeenCalled();
  });

  it("shows the intact state when the report passes", async () => {
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    await user.click(await screen.findByRole("button", { name: "Run check" }));

    expect(await screen.findByText("No orphans, chain intact")).toBeInTheDocument();
  });

  it("shows the broken state when the report finds orphans", async () => {
    mocks.runIntegrityReport.mockResolvedValue({
      ok: false,
      orphans: { "billing.accounts->crm.customers": 3 },
      audit_chain_intact: false,
      audit_entries: 12,
    });
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    await user.click(await screen.findByRole("button", { name: "Run check" }));

    expect(await screen.findByText("3 orphaned row(s)")).toBeInTheDocument();
    expect(screen.getByText("billing.accounts \u2192 crm.customers")).toBeInTheDocument();
  });

  it("shows the error when the request fails", async () => {
    mocks.runIntegrityReport.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();

    renderWithQuery(<AuditPage />);

    await user.click(await screen.findByRole("button", { name: "Run check" }));

    expect(await screen.findByText(/could not reach the service/i)).toBeInTheDocument();
  });
});
