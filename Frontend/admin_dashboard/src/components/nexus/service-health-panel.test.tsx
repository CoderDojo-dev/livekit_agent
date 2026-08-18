import { screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/test/render";
import { ServiceHealthPanel } from "./service-health-panel";
import type { ServiceHealthReport, ServiceHealthStatus } from "@/lib/api/service-health.server";

const mocks = vi.hoisted(() => ({ getServiceHealth: vi.fn() }));

vi.mock("@/lib/api/service-health.server", () => ({
  getServiceHealth: mocks.getServiceHealth,
}));

const SERVICE = {
  id: "knowledge-service",
  name: "knowledge-service",
  domain: "retrieval",
  monitoring_configured: true,
  probe_kind: "readiness",
  required: true,
  status: "degraded",
  reason: "service_reported_degraded",
  latency_ms: 42,
} as const;

const baseReport = (overrides: Record<string, unknown> = {}): ServiceHealthReport => ({
  schema_version: 1,
  overall: "reachable",
  checked_at: new Date().toISOString(),
  cache_ttl_ms: 15000,
  probe_timeout_ms: 1500,
  business_api_liveness: { status: "reachable", reason: "request_served" },
  services: [],
  ...overrides,
});

function defaultData() {
  return baseReport({ services: [SERVICE] });
}

function setMockData(data: ServiceHealthReport) {
  mocks.getServiceHealth.mockResolvedValue(data);
}

beforeEach(() => {
  setMockData(defaultData());
});

describe("service health panel", () => {
  it("does not query or reveal topology to non-admins", () => {
    renderWithQuery(<ServiceHealthPanel isAdmin={false} />);
    expect(screen.getByText("Service health restricted")).toBeInTheDocument();
    expect(mocks.getServiceHealth).not.toHaveBeenCalled();
  });

  it("renders truthful service state, reason and latency", async () => {
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    expect(await screen.findByText("knowledge-service")).toBeInTheDocument();
    expect(screen.getAllByText("Degraded").length).toBeGreaterThan(0);
    expect(screen.getByText("42 ms")).toBeInTheDocument();
    expect(screen.getByText("service_reported_degraded")).toBeInTheDocument();
  });

  it("renders the business-api liveness line separately", async () => {
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    await screen.findByText("knowledge-service");
    expect(screen.getByText(/business-api liveness reachable/)).toBeInTheDocument();
  });

  it("shows required/optional and monitoring labels", async () => {
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    await screen.findByText("knowledge-service");
    expect(screen.getByText(/monitoring configured/)).toBeInTheDocument();
    expect(screen.getByText(/required/)).toBeInTheDocument();
  });

  it("uses probe_kind and latency in the freshness subtitle", async () => {
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    await screen.findByText("knowledge-service");
    expect(screen.getByText(/1500 ms probe budget/)).toBeInTheDocument();
    expect(screen.getByText(/readiness probe/)).toBeInTheDocument();
  });

  it("renders a none-probe row without a status chip", async () => {
    setMockData(
      baseReport({
        overall: "unknown",
        services: [
          {
            id: "agent-worker",
            name: "agent-worker",
            domain: "orchestration",
            monitoring_configured: false,
            probe_kind: "none",
            required: true,
            status: "unknown",
            reason: "no_http_health_contract",
            latency_ms: null,
          },
        ],
      }),
    );
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    expect(await screen.findByText("agent-worker")).toBeInTheDocument();
    expect(screen.getByText(/monitoring not configured/)).toBeInTheDocument();
    expect(screen.getByText(/no probe/)).toBeInTheDocument();
  });

  it("renders duplicate names and allows differentiating by id", async () => {
    setMockData(
      baseReport({
        services: [
          { ...SERVICE, id: "knowledge-service", status: "reachable", reason: "probe_succeeded" },
          { ...SERVICE, id: "knowledge-service-alt", status: "unavailable", reason: "timeout" },
        ],
      }),
    );
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    await screen.findAllByText("knowledge-service");
    expect(screen.getAllByText("knowledge-service").length).toBe(2);
    expect(screen.getAllByRole("listitem").length).toBe(2);
  });

  it("never renders internal URLs, credentials, or response bodies", async () => {
    setMockData(
      baseReport({
        services: [
          {
            id: "x",
            name: "x",
            domain: "d",
            monitoring_configured: true,
            probe_kind: "liveness",
            required: true,
            status: "unavailable",
            reason: "health_auth_misconfigured",
            latency_ms: 10,
          },
        ],
      }),
    );
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    await screen.findByText("x");
    const text = document.body.textContent ?? "";
    expect(text).not.toContain("http://");
    expect(text).not.toContain("authorization");
    expect(text).not.toContain("x-api-key");
  });

  it("shows the no-probes state without claiming health", async () => {
    setMockData(baseReport({ services: [] }));
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    expect(await screen.findByText("No probes configured")).toBeInTheDocument();
    expect(screen.queryByText(/reachable/i)).not.toBeInTheDocument();
  });

  it("renders an error-only snapshot when the first load fails", async () => {
    mocks.getServiceHealth.mockRejectedValue(new Error("boom"));
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    expect(await screen.findByText(/Could not load/, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.queryByText("knowledge-service")).not.toBeInTheDocument();
  });

  it("retains rows and surfaces a background error", async () => {
    mocks.getServiceHealth
      .mockResolvedValueOnce(
        baseReport({ services: [{ ...SERVICE, status: "reachable", reason: "probe_succeeded" }] }),
      )
      .mockRejectedValue(new Error("boom"));
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    expect(await screen.findByText("knowledge-service")).toBeInTheDocument();
    const btn = screen.getByRole("button", { name: /refresh/i });
    fireEvent.click(btn);
    expect(
      await screen.findByText(
        /Could not reach the service\. Check that business-api is running\./,
        {},
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("knowledge-service")).toBeInTheDocument();
  });

  it("signals an in-flight refresh via aria-busy and a live region", async () => {
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    await screen.findByText("knowledge-service");
    const liveRegion = screen.getByText(/Service health/);
    expect(liveRegion).toHaveAttribute("aria-live", "polite");
  });

  it("refetches on Refresh", async () => {
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    await screen.findByText("knowledge-service");
    mocks.getServiceHealth.mockClear();
    const btn = screen.getByRole("button", { name: /refresh/i });
    fireEvent.click(btn);
    await waitFor(() => expect(mocks.getServiceHealth).toHaveBeenCalled());
  });

  it("warns stale after 120 seconds", async () => {
    setMockData(
      baseReport({
        checked_at: new Date(Date.now() - 130_000).toISOString(),
        services: [SERVICE],
      }),
    );
    renderWithQuery(<ServiceHealthPanel isAdmin={true} />);
    expect(await screen.findByText("knowledge-service")).toBeInTheDocument();
    expect(screen.getByText(/Stale snapshot/)).toBeInTheDocument();
  });
});
