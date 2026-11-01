from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ai_engine.layer3 import detector


@pytest.mark.parametrize(("response", "expected"), [("YES", True), ("NO", False)])
def test_layer3_parses_exact_llm_verdict(
    monkeypatch: pytest.MonkeyPatch, response: str, expected: bool
) -> None:
    invoke = Mock(return_value=SimpleNamespace(content=response))
    monkeypatch.setattr(detector, "llm", SimpleNamespace(invoke=invoke))

    result = detector.is_danger_l3(
        [{"role": "user", "content": "What is the capital of France?"}]
    )

    assert result is expected
    invoke.assert_called_once()


def test_layer3_rejects_non_binary_llm_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoke = Mock(return_value=SimpleNamespace(content="Probably safe"))
    monkeypatch.setattr(detector, "llm", SimpleNamespace(invoke=invoke))

    with pytest.raises(ValueError, match="Unexpected LLM response"):
        detector.is_danger_l3([{"role": "user", "content": "hello"}])


@pytest.mark.parametrize("conversation", [[], "not a list", [{"role": "user"}]])
def test_invalid_conversation_short_circuits_without_llm(
    monkeypatch: pytest.MonkeyPatch, conversation: object
) -> None:
    invoke = Mock()
    monkeypatch.setattr(detector, "llm", SimpleNamespace(invoke=invoke))

    assert detector.is_danger_l3(conversation) is False
    invoke.assert_not_called()
