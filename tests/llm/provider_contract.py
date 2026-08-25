"""Abstract contract test suite (CAP-5).

Every adapter - including the mock - must pass these. A new adapter earns
trust by subclassing and providing an instance via the `provider` fixture;
nothing here may depend on adapter internals.
"""

from abc import ABC, abstractmethod

from newsagent.llm.base import LLMProvider
from newsagent.llm.types import ArticleInput, DigestVoice, Refusal, RelevanceScore, SummaryResult

ON_TOPIC_ARTICLE = ArticleInput(
    title="Advances in artificial intelligence research",
    text=(
        "Artificial intelligence systems continue to improve. Researchers in "
        "artificial intelligence published new results about intelligence "
        "benchmarks and artificial neural networks this week."
    ),
)

OFF_TOPIC_ARTICLE = ArticleInput(
    title="Championship final ends in dramatic penalty shootout",
    text=(
        "The football final was decided on penalties after a tense goalless "
        "draw. Supporters celebrated deep into the night across the city."
    ),
)

JUNK_ARTICLE = ArticleInput(title="x", text="   ")

TOPIC = "artificial intelligence"


class ProviderContractSuite(ABC):
    @abstractmethod
    def make_provider(self) -> LLMProvider: ...

    # -- CAP-1: calibrated anchored scoring ---------------------------------

    def test_on_topic_article_scores_above_anchor(self):
        result = self.make_provider().score_relevance(ON_TOPIC_ARTICLE, TOPIC)
        assert isinstance(result, RelevanceScore)
        assert result.score >= 0.7

    def test_off_topic_article_scores_below_anchor(self):
        result = self.make_provider().score_relevance(OFF_TOPIC_ARTICLE, TOPIC)
        assert isinstance(result, RelevanceScore)
        assert result.score <= 0.3

    def test_score_is_within_scale(self):
        for article in (ON_TOPIC_ARTICLE, OFF_TOPIC_ARTICLE):
            result = self.make_provider().score_relevance(article, TOPIC)
            assert isinstance(result, RelevanceScore)
            assert 0.0 <= result.score <= 1.0

    # -- CAP-2: structured Hebrew summary -----------------------------------

    def test_summarize_returns_structured_result(self):
        result = self.make_provider().summarize(ON_TOPIC_ARTICLE)
        assert isinstance(result, SummaryResult)
        assert result.summary_he
        assert result.title_he
        assert result.source_language
        assert result.reading_time_minutes >= 1

    def test_summarize_returns_paragraphs_and_interestingness(self):
        result = self.make_provider().summarize(ON_TOPIC_ARTICLE)
        assert isinstance(result, SummaryResult)
        assert len(result.paragraphs_he) >= 1
        assert all(b for b in result.paragraphs_he)
        assert 0.0 <= result.interestingness <= 1.0

    def test_compose_digest_voice_returns_intro_and_joke(self):
        result = self.make_provider().compose_digest_voice(
            ["AI model breaks record", "New space telescope launched"]
        )
        assert isinstance(result, DigestVoice)
        assert result.intro_he
        assert result.dad_joke_he

    def test_compose_digest_voice_refuses_empty_headlines(self):
        assert isinstance(self.make_provider().compose_digest_voice([]), Refusal)

    # -- CAP-6: explicit refusal, distinct from failure ---------------------

    def test_junk_input_is_refused_not_raised(self):
        provider = self.make_provider()
        assert isinstance(provider.score_relevance(JUNK_ARTICLE, TOPIC), Refusal)
        assert isinstance(provider.summarize(JUNK_ARTICLE), Refusal)

    # -- batch default -------------------------------------------------------

    def test_batch_scoring_matches_single_scoring(self):
        provider = self.make_provider()
        batch = provider.score_relevance_many([ON_TOPIC_ARTICLE, OFF_TOPIC_ARTICLE], TOPIC)
        assert len(batch) == 2
        assert isinstance(batch[0], RelevanceScore)
        assert isinstance(batch[1], RelevanceScore)
