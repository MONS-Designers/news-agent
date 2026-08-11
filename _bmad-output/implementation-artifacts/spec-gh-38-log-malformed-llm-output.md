---
title: 'Diagnostic logging for malformed external-LLM output'
type: 'bugfix'
created: '2026-08-06'
status: 'done'
baseline_commit: 'baf501f1350cf42f096a22492a268921c71bfc01'
review_loop_iteration: 1
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** ~41% of `summarize` calls against `z-ai/glm-5.2` fail with `external LLM returned malformed output`, and the raw model response is discarded — so nobody can tell whether the model fences its JSON, truncates mid-object, returns a bad field type, or never returned a usable response at all. Worse, `_request`'s single `except` collapses three structurally different failures into one message.

**Approach:** Make the failure legible: name which stage failed and log the evidence that stage actually has. No behavior change — same exceptions, same statuses, same retry semantics.

## Boundaries & Constraints

**Always:**
- Distinguish the three failure stages: response-envelope extraction, `json.loads(content)`, and the typed-result `build(data)`. A log line that cannot tell these apart does not solve this issue.
- Truncate logged payloads to a bounded prefix + suffix with the full length reported — a raw response may be arbitrarily long.
- Log at `WARNING` via `logging.getLogger(__name__)`, matching every existing call site. No new logging config; GH #39 already owns the destination.
- Log the model name alongside the failure — the same code serves multiple configured models.

**Ask First:**
- Any live call to the paid OpenRouter endpoint — every run, with an estimated cost.
- Changing which exceptions map to which `LLMError` subclass, or their `transient` flag.

**Never:**
- Do not log request headers or the `Authorization` bearer token.
- Do not fix the 41% rate here — no fence-stripping, no `response_format`, no JSON-repair, no prompt changes. Diagnosis only; the fix is deferred work.
- Do not add an attempt counter or terminal status for repeatedly-failing articles — separately deferred.
- Do not make `http_llm_client.py` wrap or translate exceptions; its contract is that they propagate untouched. Logging is allowed; error mapping is not.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Success | Model returns valid JSON matching the schema | No new log output at all | N/A |
| Bad envelope | HTTP 200 whose body has no `choices` (OpenRouter returns errors this way) | WARNING naming the envelope stage + truncated response body | `LLMProviderError`, unchanged |
| Fenced JSON | `content` is ` ```json {...}``` ` | WARNING naming the parse stage + truncated `content` + its length | `LLMProviderError`, unchanged |
| Truncated JSON | `content` ends mid-object | WARNING naming the parse stage; the length makes truncation visible | `LLMProviderError`, unchanged |
| Bad schema | Valid JSON, but `bullets_he` empty or `interestingness` out of range | WARNING naming the build stage + the offending value's own message | `LLMProviderError`, unchanged |
| Null content | `"content": null` in the envelope (tool call / filtered / reasoning model) | WARNING naming the json stage and the received type | `LLMProviderError` — must NOT escape as `TypeError` |
| Long response | `content` is 50k characters | Log line stays bounded; full length still reported | N/A |
| Auth failure | HTTP 401 | Unchanged — no new logging, no token in output | `LLMProviderError`, unchanged |
| Suggestions path | `suggestions/llm.py` hits a bad envelope | Same envelope WARNING — it shares the client | Caller's own error, unchanged |

</frozen-after-approval>

## Code Map

- `src/newsagent/llm/external.py:49-80` -- `_request`. The single `except` to split into stages; `build` runs in the same `try` as the network call today.
- `src/newsagent/http_llm_client.py:29-30` -- `response.json()["choices"][0]["message"]["content"]`. The only place with access to the raw response body; shared with `suggestions/llm.py`, so it stays domain-free.
- `src/newsagent/llm/errors.py` -- `LLMProviderError` is non-transient; unchanged.
- `src/newsagent/pipeline/summarize.py:62` -- existing `logger.warning("Summarize failed for article %s: ...")`. The new lines land immediately before it; the pipeline is single-threaded, so they stay adjacent.
- `src/newsagent/suggestions/llm.py:56` -- second caller of the shared client; inherits envelope logging.
- `tests/llm/test_external_provider.py` -- existing adapter tests; convention is `httpx.MockTransport` plus a `_provider_with_handler` helper.
- `tests/test_http_llm_client.py` -- existing shared-client tests, same MockTransport convention.

## Tasks & Acceptance

**Execution:**
- [x] `src/newsagent/http_llm_client.py` -- Add a module logger; on `KeyError`/`IndexError`/`TypeError`/`ValueError` while extracting `content`, log a truncated response body at WARNING and re-raise untouched.
- [x] `src/newsagent/llm/external.py` -- Split `_request`'s single `try` so the network/envelope call, `json.loads`, and `build` each map to their own `except`; log truncated `content`, its length, and the model on the latter two. Same exception types out.
- [x] `src/newsagent/llm/external.py` -- Add a small shared truncation helper (prefix + suffix + full length); keep it private to the module.
- [x] `tests/llm/test_external_provider.py` -- Cover the matrix: bad envelope, fenced JSON, truncated JSON, bad schema, long response, and that success logs nothing. Assert via `caplog`.
- [x] `tests/test_http_llm_client.py` -- Cover envelope logging plus the invariant that no header or token value appears in log output.

**Acceptance Criteria:**
- Given a summarize failure of any of the three kinds, when the pipeline runs, then the log names which stage failed — enough to pick a fix without guessing.
- Given `NEWSAGENT_LOG_DESTINATION=file`, when a run completes, then every failure's evidence is in that file — this is what GH #39 was built for.
- Given any failure, when the log is inspected, then no `Authorization` header or token value appears anywhere in it.
- Given the same inputs as before this change, when the pipeline runs, then article statuses, retry behavior, and raised exception types are byte-for-byte identical — this story adds observability only.

## Spec Change Log

- **2026-08-06 — iteration 1, triggered by adversarial review.**
  - *Finding (patch, but an acceptance violation):* splitting the single `try` silently narrowed the caught exception set. The dedicated JSON block caught `json.JSONDecodeError` only, but `json.loads` raises **`TypeError`** when `content` is not a str — which OpenAI-compatible endpoints produce routinely (`"content": null` for tool calls, filtered completions, and reasoning models that answer in a sibling field). Reproduced: `provider.summarize()` raised a bare `TypeError` instead of `LLMProviderError`.
  - *Blast radius:* `base.py::_run` and `summarize_relevant_articles` both catch only `LLMError`, so the `TypeError` aborted the whole summarize stage mid-loop. The triggering article was never marked `error`, stayed in `_SUMMARIZABLE`, and would crash the stage again on every future run — one article poisoning all the others. Directly violated this spec's "statuses, retry behavior, and exception types are byte-for-byte identical".
  - *Amended:* the JSON stage now catches `(TypeError, ValueError)`, matching the original coverage for that operation, and logs the received type. `_clip` accepts any object. Matrix and tests gained a non-string-content row.
  - *KEEP:* the stage split itself — it is what makes the 41% legible, and it was correct apart from the narrowed tuple. Also keep the both-ends clip; head-only would have hidden that the fenced payloads were complete rather than truncated.
  - *Also tuned:* `_CONTENT_LOG_CHARS` 300 -> 500 after the live run showed real responses run 531-721 chars, i.e. the original window clipped exactly the payloads worth replaying offline.

## Design Notes

**Why the envelope stage is the interesting one.** `send_chat_completion` does `response.json()["choices"][0]["message"]["content"]` after `raise_for_status()`. OpenRouter returns upstream provider failures as **HTTP 200 with an `{"error": ...}` body and no `choices`**, so those raise `KeyError` *inside the client* and surface as "malformed output" — indistinguishable today from a model that fenced its JSON. The issue's suggested fix ("log the raw `content`") cannot cover this case, because `content` was never assigned. If a meaningful share of the 41% is this, the eventual fix is error handling, not prompt engineering.

**Truncation shape.** Log `len(content)` plus a bounded head and tail rather than a middle slice — truncation shows up at the tail, fencing at the head.

## Verification

**Commands:**
- `python -m pytest tests/ -q` -- expected: no new failures beyond the 5 known `.env`-sensitive ones.
- `python -m ruff check src tests` -- expected: clean.
- `python -m mypy` -- expected: no new errors.

**Manual checks (if no CLI):**
- Confirm by reading the diff that no code path logs `headers`, `auth_token`, or the request `payload`.
