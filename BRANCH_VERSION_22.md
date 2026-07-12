# version_22 — The Third Working Version with Persistence Fixes

## Description
The third working version with persistence fixes: mention changes & patches & updates added to this new branch.

## Changes & Patches & Updates

### 1. Client Widget — LiveKit Agents UI Rewrite
- Complete rewrite from bare `livekit-client` Room integration to `@livekit/components-react` + shadcn/ui + Tailwind v4
- New `AgentSessionProvider` pattern with `AgentAudioVisualizerAura`, `AgentControlBar`, `StartAudioButton`
- Dark-mode theme with OKLCH color tokens (navy/slate/cyan), Geist font, animated aurora visualizer
- Secure-session badge, multilingual footer (Français · العربية · English)
- Custom `TokenSource` integration with the existing token-service
- **New dependencies**: `@livekit/components-react`, `lucide-react`, `motion`, `class-variance-authority`, `clsx`, `tailwind-merge`, `@fontsource-variable/geist`, `@base-ui/react`
- **New dev dependencies**: `tailwindcss v4`, `@tailwindcss/vite`, `@types/node`
- Path alias `@/` → `src/`; ES2022 target; host `0.0.0.0`
- **19 new files**: agents-ui components (audio visualizers, control bar, session provider, disconnect button, track controls, start-audio button, shader-toy), UI components (button, select, toggle), hooks (audio visualizer, control bar), lib utils, index.css

### 2. Consent Task — LLM-Generated Multilingual Prompts
- Rewritten from pre-recorded `session.say()` prompts to LLM-generated multilingual consent questions via `generate_reply`
- Language-locked instructions: FR/AR/EN prompts embedded directly in task
- `record_consent` function tool signature: now takes `context: RunContext` + `consent_given: bool`
- No more `asyncio.Task` watchdog/timer; fully deterministic LLM flow
- Consent refusal triggers `generate_reply` for polite acknowledgment (no recording)

### 3. Triage Agent — Language-Locked Instructions
- Instructions tightened: `"You MUST speak ONLY in {language}. Never switch to another language."`
- `ConsentTask` receives `chat_ctx.copy(exclude_instructions=True)` to prevent instruction bleed
- Greeting reverted from `session.say()` to `generate_reply` with language-locked instructions
- Refactored `_LANG_NAMES` dict for cleaner language resolution

### 4. Voice-Flow Test — Updated Assertions
- `test_voice_flow.py`: assertions updated from checking `DEADLINE_S`/`self._done` patterns to checking `function_tool`, `async def on_enter`, and `self.complete(`

## Files Affected (30 files, +8686/-786)

| File | Status | Change |
|------|--------|--------|
| `apps/client-widget/src/App.tsx` | Modified | Full rewrite to AgentSessionProvider + visualizer + control bar |
| `apps/client-widget/index.html` | Modified | Dark class, new title "Telecom Assist", theme-color meta |
| `apps/client-widget/package.json` | Modified | Added 10 new deps + tailwindcss/vite |
| `apps/client-widget/package-lock.json` | Modified | Lockfile update |
| `apps/client-widget/src/main.tsx` | Modified | Import index.css instead of styles.css |
| `apps/client-widget/tsconfig.json` | Modified | ES2022, path aliases, bundler resolution |
| `apps/client-widget/vite.config.ts` | Modified | Tailwind plugin, path aliases, host 0.0.0.0 |
| `apps/client-widget/src/styles.css` | **Deleted** | Replaced by index.css |
| `apps/client-widget/components.json` | **New** | shadcn/ui configuration |
| `apps/client-widget/src/index.css` | **New** | Tailwind v4 + OKLCH theme tokens |
| `apps/client-widget/tailwind.config.js` | **New** | Tailwind config (dark mode, content paths) |
| `apps/client-widget/src/lib/utils.ts` | **New** | cn() utility (clsx + tailwind-merge) |
| `apps/client-widget/src/components/agents-ui/*` | **New** | 10 agents-ui components |
| `apps/client-widget/src/components/ui/*` | **New** | 3 shadcn ui components |
| `apps/client-widget/src/hooks/agents-ui/*` | **New** | 3 agents-ui hooks |
| `apps/agent-worker/src/tasks/consent_task.py` | Modified | LLM-generated multilingual prompts; new function tool signature |
| `apps/agent-worker/src/agents/triage_agent.py` | Modified | Language-locked instructions; chat_ctx isolation |
| `apps/agent-worker/tests/interruption/test_voice_flow.py` | Modified | Updated task pattern assertions |
