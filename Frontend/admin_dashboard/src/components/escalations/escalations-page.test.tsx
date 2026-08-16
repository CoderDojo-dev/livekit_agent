import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Escalation } from "@/lib/api/escalations.server";
import { renderWithQuery } from "@/test/render";
import { EscalationsPage, escalationKeys } from "./escalations-page";

const mocks = vi.hoisted(() => ({
  listEscalations: vi.fn(),
  closeEscalation: vi.fn(),
}));

vi.mock("@/lib/api/escalations.server", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/escalations.server")>(
    "@/lib/api/escalations.server",
  );

  return {
    ...actual,
    listEscalations: mocks.listEscalations,
    closeEscalation: mocks.closeEscalation,
  };
});

function escalation(overrides: Partial<Escalation> = {}): Escalation {
  return {
    id: "esc-1",
    session_id: "session-1",
    trigger: "customer_request",
    target: "human_advisor",
    resolution: null,
    dossier: {},
    created_at: "2026-01-02T03:04:05Z",
    customer_id: "cust-42",
    customer_name: "Ada Lovelace",
    customer_vip: false,
    ...overrides,
  };
}

beforeEach(() => {
  mocks.listEscalations.mockResolvedValue({ escalations: [escalation()] });

  mocks.closeEscalation.mockResolvedValue(
    escalation({
      resolution: "resolved",
    }),
  );
});

describe("escalations page", () => {
  it("renders customer identity and VIP only for true", async () => {
    mocks.listEscalations.mockResolvedValue({
      escalations: [
        escalation({
          id: "vip",
          customer_vip: true,
        }),
        escalation({
          id: "regular",
          customer_name: "Grace Hopper",
          customer_vip: false,
        }),
        escalation({
          id: "unknown-vip",
          customer_name: "Katherine Johnson",
          customer_vip: null,
        }),
      ],
    });

    renderWithQuery(<EscalationsPage />);

    expect((await screen.findAllByText("Ada Lovelace")).length).toBeGreaterThan(0);

    const adaRow = screen.getByRole("button", { name: /ada lovelace/i });
    const graceRow = screen.getByRole("button", { name: /grace hopper/i });
    const katherineRow = screen.getByRole("button", { name: /katherine johnson/i });

    expect(within(adaRow).getByText("VIP")).toBeInTheDocument();
    expect(within(graceRow).queryByText("VIP")).not.toBeInTheDocument();
    expect(within(katherineRow).queryByText("VIP")).not.toBeInTheDocument();

    const customerLabel = screen.getByText("Customer");
    const sessionLabel = screen.getByText("Session");
    expect(
      customerLabel.compareDocumentPosition(sessionLabel) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("renders unresolved identity safely", async () => {
    mocks.listEscalations.mockResolvedValue({
      escalations: [
        escalation({
          customer_name: null,
          customer_id: null,
          customer_vip: null,
        }),
      ],
    });

    renderWithQuery(<EscalationsPage />);

    expect((await screen.findAllByText("Customer unresolved")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it.each([
    ["Ada", "Ada Lovelace"],
    ["cust-42", "Ada Lovelace"],
  ])("filters escalations by %s", async (query, expected) => {
    mocks.listEscalations.mockResolvedValue({
      escalations: [
        escalation(),
        escalation({
          id: "esc-2",
          session_id: "session-2",
          customer_name: "Grace Hopper",
          customer_id: "cust-99",
        }),
      ],
    });
    const user = userEvent.setup();

    renderWithQuery(<EscalationsPage />);

    await screen.findByText("Grace Hopper");

    await user.type(screen.getByPlaceholderText(/search customer/i), query);

    expect(screen.getByRole("button", { name: /ada lovelace/i })).toBeInTheDocument();
    expect(screen.queryByText("Grace Hopper")).not.toBeInTheDocument();
  });

  it("closes with the selected resolution and invalidates active scope", async () => {
    const user = userEvent.setup();
    const { queryClient } = renderWithQuery(<EscalationsPage />);

    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    await user.click(await screen.findByRole("button", { name: /ada lovelace/i }));

    await user.click(screen.getByRole("button", { name: /resolved/i }));

    await waitFor(() => {
      expect(mocks.closeEscalation).toHaveBeenCalledWith({
        data: {
          id: "esc-1",
          resolution: "resolved",
        },
      });
    });

    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: escalationKeys.list("open"),
      });
    });

    expect(invalidate).not.toHaveBeenCalledWith({
      queryKey: escalationKeys.list("all"),
    });
  });

  it("shows the skeleton while the query is pending", () => {
    mocks.listEscalations.mockReturnValue(new Promise(() => {}));

    renderWithQuery(<EscalationsPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  it("shows the error and recovers when retry is pressed", async () => {
    mocks.listEscalations.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();

    renderWithQuery(<EscalationsPage />);

    expect(await screen.findByText("Could not load")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();

    mocks.listEscalations.mockResolvedValue({ escalations: [escalation()] });
    await user.click(screen.getByRole("button", { name: /try again/i }));

    expect((await screen.findAllByText("Ada Lovelace")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Could not load")).not.toBeInTheDocument();
  });

  it("shows the exact empty-state copy for the open scope", async () => {
    mocks.listEscalations.mockResolvedValue({ escalations: [] });

    renderWithQuery(<EscalationsPage />);

    expect(await screen.findByText("No open escalations")).toBeInTheDocument();
    expect(screen.getByText("Every handoff has been closed out.")).toBeInTheDocument();
  });
});
