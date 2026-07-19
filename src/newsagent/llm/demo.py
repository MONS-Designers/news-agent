"""Offline demo: score -> summarize on sample articles through the configured
provider. Run with: python -m newsagent.llm.demo (no API key required)."""

from newsagent.llm.factory import get_llm_provider
from newsagent.llm.types import ArticleInput, Refusal

SAMPLES = [
    ArticleInput(
        title="New AI model breaks benchmark records",
        text=(
            "Researchers announced a new artificial intelligence model today. "
            "The AI system outperforms previous models on language benchmarks "
            "while using less compute. Experts say artificial intelligence "
            "progress is accelerating across the industry."
        ),
    ),
    ArticleInput(
        title="Local football team wins championship",
        text=(
            "The city celebrated last night as the local football team won the "
            "national championship after a dramatic penalty shootout. Fans "
            "filled the streets and the mayor declared a day of celebration."
        ),
    ),
]


def main() -> None:
    provider = get_llm_provider()
    topic = "artificial intelligence"
    print(f"Provider: {type(provider).__name__} | Topic: {topic!r}\n")
    for article in SAMPLES:
        print(f"== {article.title}")
        result = provider.score_relevance(article, topic)
        print(f"   relevance: {result}")
        summary = provider.summarize(article)
        if isinstance(summary, Refusal):
            print(f"   refused: {summary.reason}")
        else:
            print(f"   title_he: {summary.title_he}")
            print(f"   summary_he: {summary.summary_he[:80]}...")
            print(f"   lang={summary.source_language}, ~{summary.reading_time_minutes} min\n")


if __name__ == "__main__":
    main()
