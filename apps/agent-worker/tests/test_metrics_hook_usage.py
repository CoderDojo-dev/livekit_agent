"""Cookbook 4 - exactly-once LLM usage persistence in metrics_hook.

The pre-fix hook wrote the same LLM metric twice whenever both
prompt/completion and input/output counters were present, and accepted
invalid counters (booleans, negatives). These tests pin the post-fix
contract: at most one record_llm_usage() call per accepted LLM metric
callback, with provider/model passthrough and UnknownAgent fallback.
"""
from __future__ import annotations

from types import SimpleNamespace

from observability.metrics_hook import attach_metrics


class BillingAgent:
    pass


class FakeWriter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def record_llm_usage(self, *, agent, input_tokens, output_tokens, provider, model) -> None:
        self.calls.append(
            {
                "agent": agent,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "provider": provider,
                "model": model,
            }
        )


class FakeSession:
    """Minimal stand-in for a LiveKit AgentSession: stores the handlers that
    attach_metrics registers so a test can fire metric callbacks."""

    def __init__(self, current_agent=None, *, raise_on_agent: bool = False) -> None:
        self._handlers: dict[str, object] = {}
        self._current_agent = current_agent
        self._raise_on_agent = raise_on_agent

    def on(self, event: str):
        def register(handler):
            self._handlers[event] = handler
            return handler

        return register

    @property
    def current_agent(self):
        if self._raise_on_agent:
            raise AttributeError("current_agent is unavailable")
        return self._current_agent


def _metric(metric_type: str, **fields) -> SimpleNamespace:
    return SimpleNamespace(type=metric_type, metadata=None, **fields)


def _fire(session: FakeSession, metric: SimpleNamespace) -> None:
    handler = session._handlers["metrics_collected"]
    handler(SimpleNamespace(metrics=metric))


def _collect(metric: SimpleNamespace, *, agent=None, raise_on_agent: bool = False) -> FakeWriter:
    session = FakeSession(current_agent=agent, raise_on_agent=raise_on_agent)
    writer = FakeWriter()
    attach_metrics(session, writer)
    _fire(session, metric)
    return writer


def test_one_llm_metric_produces_one_writer_call() -> None:
    writer = _collect(_metric("llm_metrics", prompt_tokens=11, completion_tokens=7), agent=BillingAgent())

    assert len(writer.calls) == 1
    assert writer.calls[0] == {
        "agent": "BillingAgent",
        "input_tokens": 11,
        "output_tokens": 7,
        "provider": None,
        "model": None,
    }


def test_prompt_completion_counters_are_accepted() -> None:
    writer = _collect(
        _metric(
            "llm_metrics",
            prompt_tokens=41,
            completion_tokens=17,
            provider="openai",
            model_name="gpt-x",
        ),
        agent=BillingAgent(),
    )

    assert writer.calls == [
        {
            "agent": "BillingAgent",
            "input_tokens": 41,
            "output_tokens": 17,
            "provider": "openai",
            "model": "gpt-x",
        }
    ]


def test_input_output_fallback_counters_are_accepted() -> None:
    writer = _collect(_metric("llm_metrics", input_tokens=5, output_tokens=3), agent=BillingAgent())

    assert len(writer.calls) == 1
    assert writer.calls[0]["input_tokens"] == 5
    assert writer.calls[0]["output_tokens"] == 3


def test_boolean_counters_are_rejected() -> None:
    writer = _collect(_metric("llm_metrics", prompt_tokens=True, completion_tokens=7), agent=BillingAgent())

    assert writer.calls == []


def test_negative_counters_are_rejected() -> None:
    writer = _collect(_metric("llm_metrics", prompt_tokens=-1, completion_tokens=7), agent=BillingAgent())

    assert writer.calls == []


def test_missing_counters_are_rejected() -> None:
    writer = _collect(_metric("llm_metrics", ttft=0.5), agent=BillingAgent())

    assert writer.calls == []


def test_non_llm_metrics_produce_no_usage_write() -> None:
    writer = _collect(_metric("tts_metrics", characters_count=10), agent=BillingAgent())

    assert writer.calls == []


def test_missing_writer_produces_no_error() -> None:
    session = FakeSession(current_agent=BillingAgent())
    attach_metrics(session, None)

    _fire(session, _metric("llm_metrics", prompt_tokens=11, completion_tokens=7))


def test_persona_is_captured_once() -> None:
    writer = _collect(
        _metric("llm_metrics", prompt_tokens=11, completion_tokens=7, input_tokens=99, output_tokens=99),
        agent=BillingAgent(),
    )

    assert len(writer.calls) == 1
    assert writer.calls[0]["agent"] == "BillingAgent"


def test_failure_to_read_current_agent_uses_unknown_agent() -> None:
    writer = _collect(
        _metric("llm_metrics", prompt_tokens=11, completion_tokens=7),
        raise_on_agent=True,
    )

    assert len(writer.calls) == 1
    assert writer.calls[0]["agent"] == "UnknownAgent"
