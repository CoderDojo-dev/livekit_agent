import { describe, expect, it, vi, beforeEach } from "vitest";
import { createElement } from "react";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AgentActivity } from "@/lib/api/agents.server";
import { renderWithQuery } from "@/test/render";

const mocks = vi.hoisted(() => ({
  getAgentActivity: vi.fn(),
}));

vi.mock("@/lib/api/agents.server", () => ({
  getAgentActivity: mocks.getAgentActivity,
  AgentActivitySchema: undefined,
}));

import { AgentsPage } from "./agents";

const ACTIVITY: AgentActivity = {
  window: {
    days: 30,
    timezone: "UTC",
    from: "2026-07-19T00:00:00.000Z",
    to: "2026-08-18T00:00:00.000Z",
  },
  definitions: {
    agent_kind: "persona_class",
    duration_kind: "non_exclusive_attributed_call_duration",
    token_source: "provider_reported",
    token_history: "forward_only_no_backfill",
  },
  totals: {
    global_unique_calls: 12,
    persona_call_attributions: 15,
    attributed_call_duration_seconds: 3600,
    provider_input_tokens: 100,
    provider_output_tokens: 200,
  },
  personas: [
    {
      persona: "BillingAgent",
      attributed_calls: 5,
      completed_calls: 4,
      attributed_call_duration_seconds: 1200,
      average_completed_call_duration_seconds: 300,
      last_observed_at: "2026-08-17T10:00:00.000Z",
      provider_input_tokens: 50,
      provider_output_tokens: 60,
      token_event_count: 2,
      daily: [
        {
          day: "2026-08-17",
          attributed_calls: 1,
          attributed_call_duration_seconds: 120,
          provider_input_tokens: 10,
          provider_output_tokens: 20,
        },
      ],
    },
  ],
};

function renderAgents() {
  return renderWithQuery(createElement(AgentsPage));
}

describe("Agents page", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    mocks.getAgentActivity.mockReset();
    mocks.getAgentActivity.mockResolvedValue(ACTIVITY);
  });

  it("shows loading skeletons while the activity query is pending", () => {
    mocks.getAgentActivity.mockReturnValue(new Promise(() => undefined));
    renderAgents();
    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Loading").length).toBeGreaterThan(0);
    expect(screen.queryByText("Billing")).not.toBeInTheDocument();
  });

  it("shows the error state with a working retry", async () => {
    mocks.getAgentActivity.mockRejectedValueOnce(new Error("boom"));
    renderAgents();
    const user = userEvent.setup();
    const messages = await screen.findAllByText(/could not reach the service/i);
    expect(messages.length).toBeGreaterThan(0);
    mocks.getAgentActivity.mockResolvedValue(ACTIVITY);
    const retryButtons = screen.getAllByRole("button", { name: /try again/i });
    await user.click(retryButtons[0]!);
    await waitFor(() => {
      expect(screen.getByText("Billing")).toBeInTheDocument();
    });
  });

  it("shows the empty state when no persona activity exists", async () => {
    mocks.getAgentActivity.mockResolvedValue({
      ...ACTIVITY,
      totals: {
        global_unique_calls: 0,
        persona_call_attributions: 0,
        attributed_call_duration_seconds: 0,
        provider_input_tokens: null,
        provider_output_tokens: null,
      },
      personas: [],
    });
    renderAgents();
    expect(await screen.findByText("No AI persona activity")).toBeInTheDocument();
    const billingRow = screen.getByRole("button", { name: /billing/i });
    expect(within(billingRow).getByText("0")).toBeInTheDocument();
    expect(within(billingRow).getByText("\u2014")).toBeInTheDocument();
  });

  it("refetches with the selected window", async () => {
    const user = userEvent.setup();
    renderAgents();
    await screen.findByText("Billing");
    expect(mocks.getAgentActivity).toHaveBeenLastCalledWith({ data: { days: 30 } });
    await user.click(screen.getByRole("button", { name: "7d" }));
    await waitFor(() => {
      expect(mocks.getAgentActivity).toHaveBeenLastCalledWith({ data: { days: 7 } });
    });
  });

  it("switches the sparkline metric to tokens", async () => {
    const user = userEvent.setup();
    renderAgents();
    await screen.findByText("Billing");
    expect(
      screen.getByRole("img", {
        name: /billing attributed call duration trend/i,
      }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tokens" }));
    expect(screen.getByRole("img", { name: /billing provider token trend/i })).toBeInTheDocument();
  });

  it("renders truthful summary cards from the backend totals", async () => {
    renderAgents();
    await screen.findByText("Billing");
    expect(screen.getByText("Unique calls")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("Persona-call attributions")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("Attributed call duration")).toBeInTheDocument();
    expect(screen.getByText("1h")).toBeInTheDocument();
    expect(screen.getAllByText("Provider tokens").length).toBeGreaterThan(0);
    expect(screen.getByText("300")).toBeInTheDocument();
  });

  it("shows Unavailable for a null token total instead of a fabricated zero", async () => {
    mocks.getAgentActivity.mockResolvedValue({
      ...ACTIVITY,
      totals: {
        global_unique_calls: 12,
        persona_call_attributions: 15,
        attributed_call_duration_seconds: 3600,
        provider_input_tokens: null,
        provider_output_tokens: null,
      },
      personas: [
        {
          ...ACTIVITY.personas[0],
          provider_input_tokens: null,
          provider_output_tokens: null,
          daily: [
            {
              ...ACTIVITY.personas[0]!.daily[0]!,
              provider_input_tokens: null,
              provider_output_tokens: null,
            },
          ],
        },
      ],
    });
    renderAgents();
    await screen.findByText("Billing");
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    const billingRow = screen.getByRole("button", { name: /billing/i });
    expect(within(billingRow).queryByText("0")).not.toBeInTheDocument();
  });

  it("opens the detail modal on keyboard activation of a row", async () => {
    const user = userEvent.setup();
    renderAgents();
    const row = await screen.findByRole("button", { name: /billing/i });
    row.focus();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "Billing" });
    expect(within(dialog).getAllByText("Attributed calls").length).toBeGreaterThan(0);
    expect(within(dialog).getByText("Share of persona-call attributions")).toBeInTheDocument();
    expect(within(dialog).getByText("Completed calls")).toBeInTheDocument();
    expect(within(dialog).getByText("Attributed call duration")).toBeInTheDocument();
    expect(within(dialog).getByText("Average completed-call duration")).toBeInTheDocument();
    expect(within(dialog).getAllByText("Input tokens").length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText("Output tokens").length).toBeGreaterThan(0);
    expect(within(dialog).getByText("Last observed")).toBeInTheDocument();
  });

  it("explains the non-exclusive duration semantics in the modal", async () => {
    const user = userEvent.setup();
    renderAgents();
    const row = await screen.findByRole("button", { name: /billing/i });
    await user.click(row);
    const dialog = await screen.findByRole("dialog", { name: "Billing" });
    expect(
      within(dialog).getByText(
        /Duration is the complete persisted call duration attributed non-exclusively/i,
      ),
    ).toBeInTheDocument();
  });

  it("renders the daily fallback table with Unavailable for null token cells", async () => {
    const user = userEvent.setup();
    renderAgents();
    const row = await screen.findByRole("button", { name: /billing/i });
    await user.click(row);
    const dialog = await screen.findByRole("dialog", { name: "Billing" });
    const table = within(dialog).getByRole("table");
    expect(within(table).getByText("Day")).toBeInTheDocument();
    expect(within(table).getByText("Attributed calls")).toBeInTheDocument();
    expect(within(table).getByText("Duration")).toBeInTheDocument();
    expect(within(table).getByText("Input tokens")).toBeInTheDocument();
    expect(within(table).getByText("Output tokens")).toBeInTheDocument();
    expect(within(table).getByText("2026-08-17")).toBeInTheDocument();
    expect(within(table).getByText("2m")).toBeInTheDocument();
  });

  it("renders the page at a 320px viewport without crashing", async () => {
    const originalWidth = window.innerWidth;
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      writable: true,
      value: 320,
    });
    try {
      renderAgents();
      expect(await screen.findByText("Billing")).toBeInTheDocument();
      expect(screen.getByText("Unique calls")).toBeInTheDocument();
      expect(screen.getByText("Persona-call attributions")).toBeInTheDocument();
      expect(screen.getByText("Attributed call duration")).toBeInTheDocument();
      expect(screen.getAllByText("Provider tokens").length).toBeGreaterThan(0);
    } finally {
      Object.defineProperty(window, "innerWidth", {
        configurable: true,
        writable: true,
        value: originalWidth,
      });
    }
  });

  it("keeps the old sessions/turns copy out of the table", async () => {
    renderAgents();
    await screen.findByText("Billing");
    expect(screen.queryByText("Time spent")).not.toBeInTheDocument();
    expect(screen.queryByText("Caller turns")).not.toBeInTheDocument();
    expect(screen.queryByText("Share of turns")).not.toBeInTheDocument();
    expect(screen.queryByText("Agent sessions")).not.toBeInTheDocument();
    expect(screen.queryByText("Coverage")).not.toBeInTheDocument();
  });
});
