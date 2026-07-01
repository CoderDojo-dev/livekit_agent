# Patch-Set 3 — Real integrations behind CONNECTOR_MODE (tester report)

The highest-impact batch: the mock side-effects become **real code paths**, all gated on
`CONNECTOR_MODE` (default `mock`) so nothing changes in dev/CI and live binds purely via `.env`
(placeholders shipped in Patch-Set 1).

## Report items closed (6)
| # | Item | What changed |
|---|---|---|
| 3 🔴 | Stub adapters (NotImplementedError) | `packages/integration-adapters`: **Mock + Live** impls for `BillingPort`, `BalancePort` (OCS), `PaymentPort`, `CrmPort`, `NmsPort`, `TicketingPort` + a `factory` (`get_billing_adapter()` …). Live uses httpx; **falls back to mock if the URL is unset** |
| 4 🔴 | No real GLPI client | ticketing MCP: `LiveGlpiClient` (GLPI REST: initSession → Ticket CRUD) + `get_glpi_client()` factory; the tools now use the factory (mock unless `CONNECTOR_MODE=live` + `GLPI_*` set). The Postgres mirror still answers lookups |
| 5 🔴 | No real SMS/WhatsApp/Email | notification `channels.py`: `TwilioChannel` (SMS/WhatsApp via REST, no SDK) + `SmtpEmailChannel` (stdlib, off-thread) + a `get_channel` factory that picks live when configured, **else mock** |
| 10 🔴 | Fake execution dispatch | `executor.dispatch` routes `EXECUTE_PAYMENT`/`PAYMENT_DEFERRAL`/`TOP_UP` through the live adapters when `CONNECTOR_MODE=live`; **mock keeps the exact prefixed reference** so behaviour/tests are unchanged. `service.execute` now passes `customer_id` + `idempotency_key` through |
| 11 🟠 | notification-client stub (log-only) | `ChannelStrategyNotifier.send` now **POSTs to the notification-service** over HTTP (fault-tolerant: logs, never raises) |
| 2 🟠 | messaging-gateway MCP empty | new FastMCP server (`:8203/mcp`) exposing `send_sms` / `send_whatsapp`, which call the notification-service |

## Design (why it's safe)
- **Mock by default, live by config.** Every factory reads `CONNECTOR_MODE`; if `live` is selected but
  the endpoint/credentials are missing, it **degrades to mock** rather than crashing — a
  half-configured staging box still runs.
- **One-module blast radius** (Blueprint ADR 5.4): a vendor API change touches exactly one adapter.
- **No behaviour change in mock mode** — the execution reference format, the GLPI mock, and the
  notification mock are byte-for-byte what they were, so all existing suites pass untouched.

## Turn it live (staging, in `.env`)
```bash
CONNECTOR_MODE=live
BILLING_ADAPTER_URL=https://billing.internal/... OCS_ADAPTER_URL=... PAYMENT_ADAPTER_URL=...
GLPI_BASE_URL=https://glpi.tt/apirest.php  GLPI_APP_TOKEN=...  GLPI_USER_TOKEN=...
TWILIO_ACCOUNT_SID=...  TWILIO_AUTH_TOKEN=...  TWILIO_SMS_FROM=+216...  # or SMTP_HOST=... for email
```

## Verification (mock paths, offline)
integration-adapters **4** · execution **5** (dispatch still `PAY-…`) · notification **6** · ticketing
**2** — all green; the GLPI factory + every adapter factory return the **Mock** impl when
`CONNECTOR_MODE` is unset. Live paths (httpx to real endpoints) compile and are exercised at integration.

## Honest scope note
- SIM (`UNBLOCK_SIM`/`REACTIVATE_SIM`) and provisioning (`CHANGE_PLAN`/`ACTIVATE_ROAMING`) have **no
  domain-core port yet**, so in live mode they return a synthesized reference (and still get ledgered +
  projected). Add a `SimPort`/`ProvisioningPort` + adapter when those live systems are bound.
- `LiveGlpiClient.list_for` returns `[]` (the Postgres mirror answers customer lookups); the GLPI
  search binding is a small later add.

## Next — Patch-Set 4 (infra/storage & ops)
Qdrant (#6), Redis (#7), MinIO (#8), Dockerfiles (#30), API gateway (#18), CI/CD (#19), Helm (#20),
DB backup (#22), secrets (#23).
