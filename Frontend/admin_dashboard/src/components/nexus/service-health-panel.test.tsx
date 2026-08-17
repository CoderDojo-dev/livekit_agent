import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/test/render";
import { ServiceHealthPanel } from "./service-health-panel";

const mocks = vi.hoisted(() => ({ getServiceHealth: vi.fn() }));
vi.mock("@/lib/api/service-health.server", () => ({ getServiceHealth: mocks.getServiceHealth }));

beforeEach(() =>
  mocks.getServiceHealth.mockResolvedValue({
    schema_version: 1,
    overall: "degraded",
    checked_at: new Date().toISOString(),
    timeout_ms: 1500,
    services: [
      {
        name: "knowledge-service",
        domain: "retrieval",
        configured: true,
        required: true,
        status: "degraded",
        reason: "service_reported_degraded",
        latency_ms: 42,
      },
    ],
  }),
);

describe("service health panel", () => {
  it("does not query or reveal topology to non-admins", () => {
    renderWithQuery(<ServiceHealthPanel isAdmin={false} />);
    expect(screen.getByText("Service health restricted")).toBeInTheDocument();
    expect(mocks.getServiceHealth).not.toHaveBeenCalled();
  });
  it("renders truthful service state", async () => {
    renderWithQuery(<ServiceHealthPanel isAdmin />);
    expect(await screen.findByText("knowledge-service")).toBeInTheDocument();
    expect(screen.getAllByText("Degraded").length).toBeGreaterThan(0);
    expect(screen.getByText("42 ms")).toBeInTheDocument();
  });
  it("shows empty configuration without claiming health", async () => {
    mocks.getServiceHealth.mockResolvedValue({
      schema_version: 1,
      overall: "unknown",
      checked_at: new Date().toISOString(),
      timeout_ms: 1500,
      services: [],
    });
    renderWithQuery(<ServiceHealthPanel isAdmin />);
    expect(await screen.findByText("No probes configured")).toBeInTheDocument();
  });
  it("renders unavailable without substituting health", async () => {
    mocks.getServiceHealth.mockResolvedValue({
      schema_version: 1,
      overall: "unavailable",
      checked_at: new Date().toISOString(),
      timeout_ms: 1500,
      services: [
        {
          name: "decision-service",
          domain: "decisioning",
          configured: true,
          required: true,
          status: "unavailable",
          reason: "timeout",
          latency_ms: 1501,
        },
      ],
    });
    renderWithQuery(<ServiceHealthPanel isAdmin />);
    expect(await screen.findByText("decision-service")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  });
});
