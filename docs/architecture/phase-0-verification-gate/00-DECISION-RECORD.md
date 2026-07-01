# Phase 0 — Verification & Decision Gate

**Decision Record (DR-0)** · Telecom AI Voice Agent Platform
Status: **APPROVED — locked for Phase 1** · Owner: Real-time Pipeline workstream
Blueprint anchor: §0 (verification discipline), §4 (technology decisions), §5.2 (ADR provider strategy), §13 (multilingual strategy), §19 Phase 0
CDC anchor: §2.4 (FR/AR/EN at comparable quality), §10.3 (multilingual parity)

> **Goal (Blueprint §19, Phase 0):** replace every open assumption with a *confirmed
> fact* before topology/providers are locked.
> **Observable exit criterion:** a short written decision record naming the **exact
> STT / TTS / turn-detector config per language**, each with its **verification source**.

This record is that deliverable. Every claim below is sourced to a live documentation
page checked on **2026-06-28**. The supporting machine-readable routing matrix
(`verification/provider_matrix.py`) and the reproducible empirical spike
(`verification/verify_providers.py`) make these decisions testable, not asserted.

---

## 0. Scope of this gate

In scope: the cloud AI provider selection (STT/LLM/TTS), the turn detector, the VAD,
and the per-language routing required by CDC §2.4. Confirmation of which **SDK symbols**
the later phases will bind to (`FallbackAdapter`, `MCPToolset`, the turn detector) and
which **domain-service contracts** are consumable as-is.

Out of scope (deferred): the running pipeline (Phase 1), the modular code tree
(Phase 2), any domain logic. No production module is created by this phase — only the
decision record and its verification evidence under `docs/architecture/`.

---

## 1. SDK surface — confirmed facts (was: assumptions)

| Item | Confirmed fact (2026-06-28) | Source |
|---|---|---|
| Core SDK version | `livekit-agents == 1.6.3`, Apache-2.0; extras include `deepgram, assemblyai, azure, google, elevenlabs, cartesia, openai, groq, silero, turn-detector, mcp`. | pypi.org/project/livekit-agents |
| Provider access path | Direct provider **plugins** (`from livekit.plugins import deepgram, elevenlabs, azure, …`). **LiveKit Inference** (the `provider/model` string gateway) requires **LiveKit Cloud transport** and is therefore **out of scope** for our self-hosted server — confirms Blueprint ADR §5.2 / correction in §2. | docs.livekit.io/agents/models · github.com/livekit/agents |
| `FallbackAdapter` (STT) | `livekit.agents.stt.FallbackAdapter(stt: list[STT], *, attempt_timeout=10.0, max_retry_per_stt=1, retry_interval=5)`. **Requires streaming STT** (raises `ValueError` for non-streaming unless wrapped in `StreamAdapter`). | docs.livekit.io/reference/python/livekit/agents/stt/fallback_adapter.html |
| `FallbackAdapter` (TTS) | `livekit.agents.tts.FallbackAdapter(tts: list[TTS], *, max_retry_per_tts=2, sample_rate=None)`. All TTS must share channel count; resamples to max sample rate. | docs.livekit.io/reference/python/livekit/agents/tts/index.html |
| `FallbackAdapter` (LLM) | `livekit.agents.llm.FallbackAdapter(llm: list[LLM], *, attempt_timeout, max_retry_per_llm, retry_interval)`. | docs.livekit.io/reference/python/livekit/agents/llm/index.html |
| MCP integration | `livekit.agents.llm.mcp.MCPToolset(*, id: str, mcp_server: MCPServer)` with `setup()` and `filter_tools(predicate)` for **allow-lists**; remote servers via `MCPServerHTTP` (URL `…/mcp` ⇒ streamable HTTP). The convenience `mcp_servers=[...]` param is **deprecated** — use explicit `MCPToolset` for stable IDs. Confirms Blueprint ADR §5.4 lock-in. | docs.livekit.io/agents/logic/tools/mcp/ · docs.livekit.io/reference/python/livekit/agents/llm/mcp.html |
| Turn detector | The **audio-native** end-of-turn model supports **14 languages incl. Arabic** (en, **ar**, de, es, fr, hi, id, it, ja, ko, nl, pt, tr, zh). For **custom (self-hosted)** deployments it runs **locally on CPU** (<500 MB RAM), no Cloud call. Accessed via `livekit.agents.inference.TurnDetector` (ships with `livekit-agents`). The standalone `livekit-plugins-turn-detector` text models are **deprecated**, and the text `MultilingualModel` **does not list Arabic** — so the audio model is mandatory for our FR/**AR**/EN scope. | docs.livekit.io/agents/build/turns/turn-detector/ · huggingface.co/livekit/turn-detector · pypi.org/project/livekit-plugins-turn-detector |
| VAD | `livekit-plugins-silero` Silero VAD, local; `min_silence_duration ≥ 0.25 s` is required by the audio turn detector (Silero default 0.55 s satisfies it). | docs.livekit.io/agents/build/turns/turn-detector/ |

**Consequence for code:** the turn detector is the one SDK touch-point whose exact
symbol is still moving (plugin → `inference.TurnDetector`). It is flagged `[verify]`
and **must be isolated behind a single wrapper file** in Phase 1
(`apps/agent-worker/src/providers/turn_detection.py`) per Blueprint §0 discipline.
See §6 VERIFY notes.

---

## 2. Language coverage — the decisive verification (CDC §2.4, Blueprint §13)

Arabic is the binding constraint; FR and EN are well covered by every candidate.
Verified facts that **shape the architecture**:

1. **Deepgram Nova-3 has a dedicated *monolingual* Arabic model** (released Jan 2026):
   17 dialect variants, **streaming + batch**, Keyterm Prompting, best-in-class WER.
   *Source: deepgram.com/learn/nova-3-arabic-speech-to-text-production-grade-stt.*
2. **Deepgram Nova-3 *multilingual* (`language=multi`) does NOT include Arabic** — its
   code-switching set is en, es, fr, de, hi, it, ja, nl, ru, pt.
   *Source: deepgram.com/learn/nova-3-multilingual-major-wer-improvements-across-languages.*
   ⇒ **Arabic must route to a dedicated `language=ar` STT instance**, not `multi`.
   This is the concrete justification for the Blueprint §13 per-language routing layer.
3. **ElevenLabs** Flash v2.5 (real-time, sub-500 ms) and Multilingual v2 both support
   **Arabic, French, English** with natural conversational voices.
   *Source: elevenlabs.io/docs/overview/capabilities/text-to-speech.*
4. **Azure Speech** provides real-time streaming STT and Neural TTS for **Arabic
   (ar-SA, ar-EG, …), French (fr-FR), English (en-US/GB)**; LiveKit ships
   `livekit-plugins-azure` STT + TTS plugins.
   *Source: learn.microsoft.com/azure/ai-services/speech-service/language-support ·
   docs.livekit.io/agents/models/stt|tts/plugins/azure/.*
5. **Audio turn detector** covers FR/AR/EN (see §1).

---

## 3. LOCKED decision — exact config **per language**

All chains are wired through `FallbackAdapter` from the first working pipeline
(Blueprint §1 "provider redundancy from day one"). Provider keys are env-driven
(Twelve-Factor); nothing hardcoded.

### 3.1 STT (streaming required by `stt.FallbackAdapter`)

| Lang | Primary | Fallback | Verification source |
|---|---|---|---|
| **fr** | Deepgram `nova-3`, `language=fr` (or `multi` for FR↔EN code-switch) | Azure STT `fr-FR` | deepgram models/languages · Azure language-support |
| **en** | Deepgram `nova-3`, `language=en` (or `multi`) | Azure STT `en-US` | same |
| **ar** | Deepgram `nova-3`, **`language=ar`** (dedicated monolingual Arabic) | Azure STT `ar-SA` (MSA; `ar-TN` if enabled in region, else `ar-SA`) | Nova-3 Arabic launch · Azure language-support |

> Routing rule: the per-turn language reported by STT selects the chain.
> `{fr,en}` may share one Deepgram `multi` instance for code-switching; `{ar}` uses its
> own `language=ar` instance, because Arabic is absent from `multi`.

### 3.2 TTS

| Lang | Primary | Fallback | Verification source |
|---|---|---|---|
| **fr** | ElevenLabs `eleven_flash_v2_5`, FR voice | Azure Neural `fr-FR-DeniseNeural` | ElevenLabs TTS capabilities · Azure voices |
| **en** | ElevenLabs `eleven_flash_v2_5`, EN voice | Azure Neural `en-US-…Neural` | same |
| **ar** | ElevenLabs `eleven_flash_v2_5`, AR voice **(pending Phase-1 listening test)** | Azure Neural `ar-SA-HamedNeural`/`ar-EG-…` | ElevenLabs Arabic · Azure Arabic TTS |

> **Open empirical item (does not block Phase 0):** the Arabic *primary* (ElevenLabs vs
> Azure) is settled by a **listening test on recorded Arabic** in Phase 1, per Blueprint
> §13 ("a listening test, not a feature-matrix checkbox"). Both are verified-supported;
> the routing abstraction lets the primary be swapped per language with **no
> re-architecture**.

### 3.3 LLM (cloud, multilingual; decided by Phase-1 benchmark per ADR §5.2)

| Role | Choice | Plugin | Note |
|---|---|---|---|
| Primary | OpenAI GPT-4.1 family (multilingual) | `livekit-plugins-openai` | Strong FR/EN; AR lifted by **structured intent/slot schemas** (§13). |
| Fallback | Google Gemini 2.x | `livekit-plugins-google` | Independent vendor for outage resilience. |

> **Assumption (one, explicit):** exact LLM model-id strings churn; they are bound in
> Phase 1 `providers/` and treated as `[verify]`. The decision here is the *provider +
> fallback topology*, which is stable. CDC §4.1 "Compréhension" is realized as the
> conversational LLM's tool-selection (ADR §5.3), so the LLM choice is orthogonal to the
> deterministic Policy engine.

### 3.4 Turn detection & VAD (shared across all languages)

| Component | Decision | Source |
|---|---|---|
| Turn detector | **Audio-native** EOU model (`livekit.agents.inference.TurnDetector`), FR/AR/EN covered, **local CPU** for self-hosted. | docs.livekit.io/agents/build/turns/turn-detector/ |
| VAD | Silero VAD (`livekit-plugins-silero`), local, `min_silence_duration ≥ 0.25 s`. | same |
| Fallback if `inference.TurnDetector` proves Cloud-coupled in the pinned build | text `MultilingualModel` for **fr/en only**; for **ar**, use STT-reported language + VAD endpointing, or semantic STT turn detection (`turn_detection="stt"` via Deepgram Flux / AssemblyAI). | huggingface.co/livekit/turn-detector |

---

## 4. Domain-service contracts — consumable as-is? (Phase-0 confirmation)

The platform is a **greenfield target system** (Blueprint locked-in correction: no prior
framework, no migration). Therefore:

- The six domain services (`context`, `knowledge`, `decision`, `policy`, `execution`,
  `notification`, Blueprint §6/§11) expose **new, narrow internal contracts** we define.
  They are *consumable-as-designed* — there is no legacy contract to reverse-engineer.
  The worker's typed `clients/` (Phase 4–9) bind to these contracts; each client owns its
  own timeout + retry (Blueprint §11.1).
- The **legacy systems** (CRM, Billing, OCS, NMS, GLPI, Payment) are reached **only**
  through per-system adapters in `packages/integration-adapters/` (Blueprint ADR §5.4).
  **Assumption (explicit):** for the pilot they are backed by the **mock telco dataset**
  the CDC mandates (real TND amounts, USSD codes, plan names), so each adapter's contract
  is defined by *our* port interface — also consumable-as-designed.
- The only **external** contract that could churn is the **LiveKit Agents SDK surface**,
  which §1 above has now pinned to `1.6.3` and isolated `[verify]` items behind single
  wrapper files.

**Conclusion:** no contract blocks Phase 1. The single `[verify]` touch-point (turn
detector) is isolated; everything else is greenfield and owned by us.

---

## 5. Exit-criterion checklist (Blueprint §19, Phase 0)

| Exit-criterion item | Satisfied by | Evidence |
|---|---|---|
| Exact **STT** config per language + source | §3.1 | table + `provider_matrix.py` |
| Exact **TTS** config per language + source | §3.2 | table + `provider_matrix.py` |
| Exact **turn-detector** config + source | §3.4 | table + `provider_matrix.py` |
| Fallback chain **per language** (resilience day one) | §3.1–3.4 (≥2 entries each) | `test_provider_matrix.py::test_every_chain_has_fallback` |
| Multilingual go/no-go **per provider per language** | §2, §3 | sourced facts; `verify_providers.py` reproduces empirically |
| Which **domain-service contracts** are consumable as-is | §4 | greenfield confirmation |
| Written decision record exists | this file | `00-DECISION-RECORD.md` |

---

## 6. VERIFY notes (carried into Phase 1)

| `[verify]` touch-point | Doc page to confirm at build | Isolated in (Phase 1) | Fallback if symbol differs |
|---|---|---|---|
| Audio turn detector symbol | docs.livekit.io/agents/build/turns/turn-detector/ | `apps/agent-worker/src/providers/turn_detection.py` | text `MultilingualModel` (fr/en) + STT-language/VAD for ar; or `turn_detection="stt"` |
| LLM model-id strings | docs.livekit.io/agents/models/ | `apps/agent-worker/src/providers/llm.py` | swap model-id within same plugin; provider topology unchanged |
| `MCPToolset` surface | docs.livekit.io/agents/logic/tools/mcp/ | `apps/agent-worker/src/mcp_clients/` (Phase 5) | `MCPServerHTTP` + `filter_tools` allow-list (already the stable path) |

---

## 7. Traceability

| CDC / Blueprint ref | Decided here | Where |
|---|---|---|
| CDC §2.4, §10.3 — FR/AR/EN parity | per-language STT/TTS/turn-detector chains | §3 |
| Blueprint §13 — per-language routing, listening-test gate | Arabic isolated to `language=ar`; AR-TTS primary deferred to listening test | §2, §3.2 |
| Blueprint ADR §5.2 — direct plugins + FallbackAdapter, no Inference | confirmed; chains defined | §1, §3 |
| Blueprint ADR §5.4 — `MCPToolset` allow-lists, adapters per system | `MCPToolset` surface confirmed | §1, §4 |
| Blueprint §19 Phase 0 — written decision record | this document | all |
