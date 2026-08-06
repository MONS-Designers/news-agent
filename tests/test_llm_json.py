"""Unit tests for markdown-fence extraction (GH #40).

The risk here is not "does it strip a fence" — it is "does it ever damage a
response that was already fine". Most of these tests guard that direction.
"""

import json

import pytest

from newsagent.llm_json import strip_code_fence

PAYLOAD = '{"summary_he": "שלום", "interestingness": 0.7}'


@pytest.mark.parametrize(
    "wrapped",
    [
        f"```json\n{PAYLOAD}\n```",
        f"```JSON\n{PAYLOAD}\n```",
        f"```\n{PAYLOAD}\n```",
        f"```json\r\n{PAYLOAD}\r\n```",
        f"  ```json\n{PAYLOAD}\n```  ",
        f"```json\n{PAYLOAD}```",
        f"```json \n{PAYLOAD}\n```",
    ],
    ids=["json-tag", "upper-tag", "no-tag", "crlf", "outer-space", "no-trailing-nl", "tag-space"],
)
def test_fenced_payloads_are_unwrapped_and_parse(wrapped: str):
    result = strip_code_fence(wrapped)

    assert json.loads(result)["interestingness"] == 0.7


def test_bare_json_is_returned_untouched():
    assert strip_code_fence(PAYLOAD) == PAYLOAD


def test_a_fence_inside_a_string_value_is_not_treated_as_a_wrapper():
    """The regex is anchored to the whole string; a model quoting a fence
    inside a field must not have its JSON mangled."""
    content = json.dumps({"summary_he": "the model said ```json here```"})

    result = strip_code_fence(content)

    assert result == content
    assert json.loads(result)["summary_he"].endswith("```")


def test_content_that_is_not_json_is_left_alone_for_the_caller_to_reject():
    """Stripping must not invent success — non-JSON stays non-JSON so the
    caller still raises, and the diagnostics still fire."""
    assert strip_code_fence("Sure! Here is your answer.") == "Sure! Here is your answer."


def test_unterminated_fence_is_left_alone():
    """A truncated response that opened a fence but never closed it is a
    genuine failure — not something to silently 'repair'."""
    content = f"```json\n{PAYLOAD[:20]}"

    assert strip_code_fence(content) == content


@pytest.mark.parametrize("value", [None, 42, {"a": 1}, ["a"]])
def test_non_string_content_passes_through_unchanged(value):
    """content is whatever the provider put in the envelope; None occurs in
    practice. The caller's json.loads must still be the thing that rejects it."""
    assert strip_code_fence(value) is value


def test_empty_string_is_safe():
    assert strip_code_fence("") == ""
