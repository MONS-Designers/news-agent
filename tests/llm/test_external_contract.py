"""ExternalLLMProvider passing the shared contract suite (CAP-5) - offline via
httpx.MockTransport, keyed on each fixed input article's title so every
contract scenario gets the canned response it needs."""

import json

import httpx
import pytest

from newsagent.config import settings
from newsagent.llm.base import LLMProvider
from newsagent.llm.external import ExternalLLMProvider
from tests.llm.provider_contract import (
    OFF_TOPIC_ARTICLE,
    ON_TOPIC_ARTICLE,
    ProviderContractSuite,
)

_ON_TOPIC_SCORE = json.dumps({"score": 0.9})
_OFF_TOPIC_SCORE = json.dumps({"score": 0.1})
_SUMMARY = json.dumps(
    {
        "summary_he": "תקציר בעברית",
        "title_he": "כותרת בעברית",
        "source_language": "en",
        "reading_time_minutes": 2,
        "paragraphs_he": ["נקודה ראשונה", "נקודה שנייה"],
        "interestingness": 0.6,
    }
)
_DIGEST_VOICE = json.dumps(
    {
        "intro_he": "בוקר טוב!",
        "dad_joke_he": "בדיחה קטנה",
    }
)


def _handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    user_content = body["messages"][-1]["content"]
    if "<TOPIC>" in user_content:
        if ON_TOPIC_ARTICLE.title in user_content:
            content = _ON_TOPIC_SCORE
        elif OFF_TOPIC_ARTICLE.title in user_content:
            content = _OFF_TOPIC_SCORE
        else:
            content = _ON_TOPIC_SCORE
    elif "<HEADLINES>" in user_content:
        content = _DIGEST_VOICE
    else:
        content = _SUMMARY
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "external_llm_base_url", "http://external-model.test")
    monkeypatch.setattr(settings, "external_llm_auth_token", "test-token")
    monkeypatch.setattr(settings, "external_llm_model", "test-model")


class TestExternalContract(ProviderContractSuite):
    def make_provider(self) -> LLMProvider:
        client = httpx.Client(transport=httpx.MockTransport(_handler))
        return ExternalLLMProvider(client=client)
