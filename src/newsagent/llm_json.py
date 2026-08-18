"""Shared normalization for JSON that arrives inside a chat completion.

Lives outside both `llm/` and `suggestions/` because both adapters parse JSON
out of the same models and hit the same provider quirks. Deliberately *not* in
`http_llm_client.py`: that module's contract is raw transport, and this is a
response-format concern.
"""

import re

# Matches a whole-string markdown code fence with an optional language tag:
# ```json\n{...}\n```  or  ```\n{...}\n```
# Anchored to the full string so a fence appearing *inside* a JSON string value
# is left alone. DOTALL because the payload spans lines.
_FENCED = re.compile(r"\A\s*```[a-zA-Z0-9_+-]*[ \t]*\r?\n(?P<body>.*?)\r?\n?\s*```\s*\Z", re.DOTALL)


def strip_code_fence(content: str) -> str:
    """Return the payload inside a markdown code fence, or `content` unchanged.

    Measured on `z-ai/glm-5.2` (GH #40): the model wraps its JSON in a
    ```json fence in roughly half of all calls despite the system prompt
    saying not to, which made ~41% of summarize calls unparseable. The JSON
    itself is complete and valid - only the wrapper is the problem.
    """
    if not isinstance(content, str):
        return content
    match = _FENCED.match(content)
    return match.group("body") if match else content
