"""LLM wrapper resilience: transient provider errors must not kill an edition."""

from __future__ import annotations

import pytest

from agewell import agents


class FakeAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class FakeClient:
    """Scripted client: `plan` maps model -> list of outcomes (exception or 'ok')."""

    def __init__(self, plan: dict[str, list]):
        self.plan = {k: list(v) for k, v in plan.items()}
        self.calls: list[str] = []
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, model, **kwargs):
        self.calls.append(model)
        outcome = self.plan.get(model, ["ok"]).pop(0) if self.plan.get(model) else "ok"
        if isinstance(outcome, Exception):
            raise outcome
        return {"model": model}


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(agents.time, "sleep", lambda *_: None)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


def test_retries_same_model_on_500_high_traffic():
    err = FakeAPIError("Error code: 500 - high traffic, please try again", status_code=500)
    client = FakeClient({"gemini-3.5-flash": [err, err, "ok"]})
    result = agents.chat_completion_with_fallback(client, "gemini-3.5-flash", messages=[])
    assert result["model"] == "gemini-3.5-flash"
    assert client.calls == ["gemini-3.5-flash"] * 3


def test_moves_to_next_gemini_model_after_exhausting_retries():
    err = FakeAPIError("503 UNAVAILABLE: model is overloaded", status_code=503)
    client = FakeClient({"gemini-3.5-flash": [err, err, err], "gemini-3.5-flash-lite": ["ok"]})
    result = agents.chat_completion_with_fallback(client, "gemini-3.5-flash", messages=[])
    assert result["model"] == "gemini-3.5-flash-lite"
    assert client.calls == ["gemini-3.5-flash"] * 3 + ["gemini-3.5-flash-lite"]


def test_quota_error_skips_retries_and_goes_to_next_model():
    err = FakeAPIError("429 RESOURCE_EXHAUSTED", status_code=429)
    client = FakeClient({"gemini-3.5-flash": [err], "gemini-3.5-flash-lite": ["ok"]})
    agents.chat_completion_with_fallback(client, "gemini-3.5-flash", messages=[])
    assert client.calls == ["gemini-3.5-flash", "gemini-3.5-flash-lite"]


def test_bad_request_is_not_retried():
    err = FakeAPIError("400 invalid argument: max_tokens 2500 too large", status_code=400)
    client = FakeClient({"gemini-3.5-flash": [err]})
    with pytest.raises(FakeAPIError):
        agents.chat_completion_with_fallback(client, "gemini-3.5-flash", messages=[])
    assert client.calls == ["gemini-3.5-flash"]


def test_falls_back_to_deepseek_when_all_gemini_models_are_down(monkeypatch):
    err = FakeAPIError("500 high traffic", status_code=500)
    gemini = FakeClient({m: [err] * 3 for m in agents.GEMINI_FALLBACK_MODELS})
    deepseek = FakeClient({})
    monkeypatch.setattr(agents, "_deepseek_client", lambda: deepseek)
    result = agents.chat_completion_with_fallback(gemini, "gemini-3.5-flash", messages=[])
    assert result["model"] == agents.DEEPSEEK_FALLBACK_MODEL
    assert deepseek.calls == [agents.DEEPSEEK_FALLBACK_MODEL]


def test_raises_last_error_when_no_fallback_available():
    err = FakeAPIError("500 high traffic", status_code=500)
    gemini = FakeClient({m: [err] * 3 for m in agents.GEMINI_FALLBACK_MODELS})
    with pytest.raises(FakeAPIError):
        agents.chat_completion_with_fallback(gemini, "gemini-3.5-flash", messages=[])
