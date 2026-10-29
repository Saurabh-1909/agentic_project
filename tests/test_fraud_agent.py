from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import fraud_agent
from fraud_agent import (
    FraudExplanation,
    RiskTier,
    TransactionInput,
    assess_transaction,
    score_transaction,
)
from google.genai import types


def test_score_transaction_with_no_triggers_is_low():
    transaction = TransactionInput(
        amount=25,
        currency="USD",
        known_device=True,
        unusual_location=False,
        transactions_last_hour=1,
        account_age_days=365,
    )

    result = score_transaction(transaction)

    assert result.score == 0
    assert result.tier is RiskTier.LOW
    assert result.triggered_rules == []


def test_score_transaction_sums_rules_and_caps_score():
    transaction = TransactionInput(
        amount=1500,
        currency="USD",
        known_device=False,
        unusual_location=True,
        transactions_last_hour=4,
        account_age_days=2,
    )

    result = score_transaction(transaction)

    assert result.score == 100
    assert result.tier is RiskTier.HIGH
    assert len(result.triggered_rules) == 5


def test_score_transaction_assigns_medium_tier_at_threshold():
    transaction = TransactionInput(
        amount=1000,
        currency="USD",
        known_device=True,
        unusual_location=True,
        transactions_last_hour=0,
        account_age_days=365,
    )

    result = score_transaction(transaction)

    assert result.score == 40
    assert result.tier is RiskTier.MEDIUM


def test_transaction_rejects_unexpected_or_invalid_fields():
    with pytest.raises(ValidationError):
        TransactionInput(
            amount=-1,
            currency="USD",
            known_device=True,
            unusual_location=False,
            transactions_last_hour=0,
            account_age_days=10,
            card_number="not-accepted",
        )


def test_agent_executes_tool_and_returns_structured_explanation(monkeypatch):
    transaction = TransactionInput(
        amount=1500,
        currency="USD",
        known_device=False,
        unusual_location=False,
        transactions_last_hour=0,
        account_age_days=30,
    )
    tool_response = SimpleNamespace(
        candidates=[SimpleNamespace(content=types.Content(role="model", parts=[]))],
        function_calls=[SimpleNamespace(name="score_transaction")],
        text=None,
    )
    model_response = SimpleNamespace(
        candidates=[SimpleNamespace(content=types.Content(role="model", parts=[]))],
        function_calls=[],
        text="The large amount and unrecognized device triggered rules.",
    )
    final_response = SimpleNamespace(
        parsed=FraudExplanation(explanation="Two transaction rules were triggered.")
    )

    class FakeModels:
        responses = [tool_response, model_response, final_response]

        def generate_content(self, **_kwargs):
            return self.responses.pop(0)

    class FakeClient:
        models = FakeModels()
        closed = False

        def __init__(self):
            self.models = FakeModels()

        def close(self):
            self.closed = True

    fake_client = FakeClient()
    monkeypatch.setattr(fraud_agent.genai, "Client", lambda **_kwargs: fake_client)

    result = assess_transaction(transaction, api_key="test-key")

    assert result.score == 45
    assert result.tier is RiskTier.MEDIUM
    assert result.triggered_rules == ["unrecognized_device", "large_amount"]
    assert result.explanation == "Two transaction rules were triggered."
    assert result.human_review_required is True
    assert fake_client.closed is True
