"""The mock provider passing the shared contract suite (CAP-4 + CAP-5),
plus mock-specific guarantees: determinism and the shared retry mechanics."""

import pytest

from newsagent.llm.base import LLMProvider
from newsagent.llm.errors import LLMProviderError, LLMTransportError
from newsagent.llm.mock import MockLLMProvider
from tests.llm.provider_contract import ON_TOPIC_ARTICLE, TOPIC, ProviderContractSuite


class TestMockContract(ProviderContractSuite):
    def make_provider(self) -> LLMProvider:
        return MockLLMProvider()


class TestMockDeterminism:
    def test_same_input_same_score(self):
        provider = MockLLMProvider()
        assert provider.score_relevance(ON_TOPIC_ARTICLE, TOPIC) == provider.score_relevance(
            ON_TOPIC_ARTICLE, TOPIC
        )

    def test_same_input_same_summary(self):
        provider = MockLLMProvider()
        assert provider.summarize(ON_TOPIC_ARTICLE) == provider.summarize(ON_TOPIC_ARTICLE)


class TestRetryMechanics:
    """CAP-3: hybrid retry is owned by the base class — verified through the
    mock's failure-injection knobs."""

    def test_transient_failures_are_retried_then_succeed(self):
        sleeps: list[float] = []
        provider = MockLLMProvider(fail_transient=2, sleep=sleeps.append)
        result = provider.summarize(ON_TOPIC_ARTICLE)
        assert not isinstance(result, LLMTransportError)
        assert len(sleeps) == 2  # two retries, with backoff

    def test_transient_failures_beyond_attempts_surface_typed_error(self):
        provider = MockLLMProvider(fail_transient=10, sleep=lambda _: None)
        with pytest.raises(LLMTransportError):
            provider.summarize(ON_TOPIC_ARTICLE)

    def test_permanent_failure_is_not_retried(self):
        sleeps: list[float] = []
        provider = MockLLMProvider(fail_permanent=True, sleep=sleeps.append)
        with pytest.raises(LLMProviderError):
            provider.summarize(ON_TOPIC_ARTICLE)
        assert sleeps == []  # no retry on non-transient errors

    def test_backoff_grows_exponentially(self):
        sleeps: list[float] = []
        provider = MockLLMProvider(fail_transient=2, backoff_seconds=1.0, sleep=sleeps.append)
        provider.summarize(ON_TOPIC_ARTICLE)
        assert sleeps == [1.0, 2.0]
