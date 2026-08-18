import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RetentionReport } from "@/lib/api/audit.server";
import { renderWithQuery } from "@/test/render";
import { RetentionPanel } from "./retention-panel";

const mocks = vi.hoisted(() => ({
  runRetention: vi.fn(),
}));

vi.mock("@/lib/api/audit.server", () => ({
  runRetention: mocks.runRetention,
}));

function retentionReport(overrides: Partial<RetentionReport> = {}): RetentionReport {
  return {
    cutoff: "2026-01-01T00:00:00+00:00",
    sessions_matched: 2,
    turns_anonymized: 7,
    dry_run: true,
    ...overrides,
  };
}

/** Faithful mock of the real server function contract: whole days, 30..3650, else reject. */
function installContractMock() {
  mocks.runRetention.mockImplementation(
    async (args: { data: { retentionDays: number; dryRun: boolean } }) => {
      const days = args.data.retentionDays;
      if (!Number.isInteger(days) || days < 30 || days > 3650) {
        throw new Error("Retention window must be a whole number between 30 and 3650 days.");
      }
      return retentionReport({ dry_run: args.data.dryRun });
    },
  );
}

beforeEach(() => {
  installContractMock();
});

function daysInput() {
  return screen.getByLabelText("Retention window (days)");
}

function purgeButtons() {
  return screen.getAllByRole("button", { name: /purge/i });
}

describe("retention panel", () => {
  it("rejects a window below 30 days", async () => {
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.clear(daysInput());
    await user.type(daysInput(), "29");
    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText(/could not reach the service/i)).toBeInTheDocument();
    expect(mocks.runRetention).toHaveBeenCalledWith({
      data: { retentionDays: 29, dryRun: true },
    });
    expect(screen.getByRole("button", { name: "Purge permanently" })).toBeDisabled();
  });

  it("rejects a window above 3650 days", async () => {
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.clear(daysInput());
    await user.type(daysInput(), "3651");
    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText(/could not reach the service/i)).toBeInTheDocument();
    expect(mocks.runRetention).toHaveBeenCalledWith({
      data: { retentionDays: 3651, dryRun: true },
    });
    expect(screen.getByRole("button", { name: "Purge permanently" })).toBeDisabled();
  });

  it("rejects a non-integer window", async () => {
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.clear(daysInput());
    await user.type(daysInput(), "90.5");
    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText(/could not reach the service/i)).toBeInTheDocument();
    expect(mocks.runRetention).toHaveBeenCalledWith({
      data: { retentionDays: 90.5, dryRun: true },
    });
    expect(screen.getByRole("button", { name: "Purge permanently" })).toBeDisabled();
  });

  it("requires a completed dry run before the purge unlocks", async () => {
    renderWithQuery(<RetentionPanel />);

    expect(screen.getByRole("button", { name: "Purge permanently" })).toBeDisabled();
  });

  it("invalidates the preview when the retention window changes", async () => {
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText(/2 session\(s\) started before/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Purge permanently" })).toBeEnabled();

    await user.clear(daysInput());
    await user.type(daysInput(), "120");

    expect(screen.queryByText(/session\(s\) started before/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Purge permanently" })).toBeDisabled();
  });

  it("cannot purge when the preview matches zero sessions", async () => {
    mocks.runRetention.mockResolvedValue(retentionReport({ sessions_matched: 0 }));
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText(/nothing would be purged/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Purge permanently" })).toBeDisabled();
  });

  it("requires the typed confirmation count to match", async () => {
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByText(/2 session\(s\) started before/i);

    await user.click(screen.getByRole("button", { name: "Purge permanently" }));

    const dialog = await screen.findByRole("dialog", { name: "Confirm permanent purge" });
    const confirm = within(dialog).getByRole("button", { name: "Purge permanently" });
    expect(confirm).toBeDisabled();

    await user.type(within(dialog).getByLabelText("Session count"), "1");
    expect(confirm).toBeDisabled();

    await user.clear(within(dialog).getByLabelText("Session count"));
    await user.type(within(dialog).getByLabelText("Session count"), "2");
    expect(confirm).toBeEnabled();
  });

  it("closes the dialog on cancel without any mutation", async () => {
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByText(/2 session\(s\) started before/i);

    await user.click(screen.getByRole("button", { name: "Purge permanently" }));
    const dialog = await screen.findByRole("dialog", { name: "Confirm permanent purge" });

    const callsBeforeCancel = mocks.runRetention.mock.calls.length;
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mocks.runRetention.mock.calls.length).toBe(callsBeforeCancel);
    expect(mocks.runRetention.mock.calls.some((call) => call[0]?.data.dryRun === false)).toBe(
      false,
    );
  });

  it("disables Preview while a dry run is pending", async () => {
    mocks.runRetention.mockReturnValue(new Promise(() => {}));
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(screen.getByRole("button", { name: "Checking..." })).toBeDisabled();
  });

  it("disables every purge button while a real purge is pending", async () => {
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByText(/2 session\(s\) started before/i);

    await user.click(screen.getByRole("button", { name: "Purge permanently" }));
    const dialog = await screen.findByRole("dialog", { name: "Confirm permanent purge" });

    await user.type(within(dialog).getByLabelText("Session count"), "2");

    mocks.runRetention.mockReturnValue(new Promise(() => {}));
    await user.click(within(dialog).getByRole("button", { name: "Purge permanently" }));

    await waitFor(() => {
      expect(purgeButtons().every((button) => (button as HTMLButtonElement).disabled)).toBe(true);
    });
    expect(screen.getByRole("button", { name: "Purging..." })).toBeDisabled();
  });

  it("does not unlock the purge when the preview fails", async () => {
    mocks.runRetention.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText(/could not reach the service/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Purge permanently" })).toBeDisabled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("sends dryRun:false for a real purge", async () => {
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByText(/2 session\(s\) started before/i);

    await user.click(screen.getByRole("button", { name: "Purge permanently" }));
    const dialog = await screen.findByRole("dialog", { name: "Confirm permanent purge" });

    await user.type(within(dialog).getByLabelText("Session count"), "2");
    await user.click(within(dialog).getByRole("button", { name: "Purge permanently" }));

    await waitFor(() => {
      expect(mocks.runRetention).toHaveBeenLastCalledWith({
        data: { retentionDays: 90, dryRun: false },
      });
    });
  });

  it("resets the preview after a successful purge", async () => {
    const user = userEvent.setup();

    renderWithQuery(<RetentionPanel />);

    await user.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByText(/2 session\(s\) started before/i);

    await user.click(screen.getByRole("button", { name: "Purge permanently" }));
    const dialog = await screen.findByRole("dialog", { name: "Confirm permanent purge" });

    await user.type(within(dialog).getByLabelText("Session count"), "2");
    await user.click(within(dialog).getByRole("button", { name: "Purge permanently" }));

    expect(
      await screen.findByText(/purge complete\. 2 session\(s\) processed/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/session\(s\) started before/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Purge permanently" })).toBeDisabled();
  });
});
