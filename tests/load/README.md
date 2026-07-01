# Load & Soak tests (Blueprint section 20)

Two release gates from the Blueprint's verification plan, for the request/response services. The voice
TTFA budget is gated separately via the OTel `telecom.agent.ttfa.seconds` histogram (Phase 11) under a
real concurrent-call run.

```bash
pip install httpx psutil

# Load: p95 latency vs budget
python tests/load/loadtest.py --url http://localhost:8108/api/v1/kpis --requests 500 --concurrency 25 --budget-ms 250

# Soak: sequential calls, watch RSS for leaks/state bleed
python tests/load/soak.py --url http://localhost:8108/health --iterations 5000
```
Both exit non-zero on failure, so they drop straight into a CI/staging gate.