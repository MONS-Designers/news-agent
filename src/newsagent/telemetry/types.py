"""Contract objects that cross the measurer / attributor / writer boundary
(ARCHITECTURE-SPINE AD-11, AD-12, AD-15) - the only shapes the transport, the
ambient context, and the sole DB writer agree on.

`CallMeasurement` is domain-free: no purpose, no article, no run - that is
`CallAttribution`'s job, read from the ambient context by the sink. Keeping
them separate is the whole point of the split (measurer doesn't know why,
attributor doesn't know how much).
"""

from dataclasses import dataclass

# `purpose` values (spine's Consistency Conventions) - call sites pass one of
# these constants, never a free-form string, so a typo can't silently create
# a new, unindexed category.
PURPOSE_FILTERING = "FILTERING"
PURPOSE_SUMMARIZING = "SUMMARIZING"
PURPOSE_DIGEST_VOICE = "DIGEST_VOICE"
PURPOSE_SUGGEST_TOPICS = "SUGGEST_TOPICS"
# Distinct from PURPOSE_SUGGEST_TOPICS (Review Finding, 2026-08-27): both are
# real, concurrent LLM calls in services/profile.py's
# _compute_and_store_suggestions, but suggest_topics ranks *existing* topics
# while suggest_new_topics invents brand-new ones - different prompts,
# different call sites, so their cost/latency/failure rate must stay
# separately queryable rather than blending into one purpose.
PURPOSE_SUGGEST_NEW_TOPICS = "SUGGEST_NEW_TOPICS"
PURPOSE_SUGGEST_ROLES = "SUGGEST_ROLES"
PURPOSE_SUGGEST_PROMPTS = "SUGGEST_PROMPTS"
# A call made with no open attribute_call() - AD-11 requires it to still be
# recorded, never silently dropped.
PURPOSE_UNATTRIBUTED = "UNATTRIBUTED"

# `outbound_calls.status` values (AD-15). `status` means "did this call
# produce usable work", not "did the HTTP succeed": `ok` and `malformed` both
# require a successful HTTP round-trip - `malformed` is a billed call whose
# body a higher layer (llm/external.py, suggestions/llm.py) found unusable
# (bad envelope, unparseable JSON, failed schema validation). Keep it
# distinct from `error` (provider/transport availability) - different fixes.
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_MALFORMED = "malformed"
STATUS_AVOIDED = "avoided"

# `outbound_runs.kind` values - one per stage invocation shape (AD-11).
KIND_FILTER = "filter"
KIND_SUMMARIZE = "summarize"
KIND_DIGEST_BUILD = "digest_build"
KIND_PROFILE_SUGGESTIONS = "profile_suggestions"
# Distinct from KIND_PROFILE_SUGGESTIONS (Review Finding, 2026-08-27):
# suggest_prompts_for_user is one cheap read-only lookup, while
# _compute_and_store_suggestions (which stays on KIND_PROFILE_SUGGESTIONS) is
# two concurrent LLM calls plus a DB write - different enough shapes that a
# query grouped by kind needs to tell them apart.
KIND_PROMPT_SUGGESTIONS = "prompt_suggestions"
KIND_TAXONOMY_SUGGESTION = "taxonomy_suggestion"

# `outbound_calls.target` (AD-17) - only "llm" is wired this revision.
TARGET_LLM = "llm"


@dataclass(frozen=True)
class CallMeasurement:
    """What the transport measured about one outbound HTTP attempt - or, for
    an avoided call (AD-15), what the caller measured standing in for it.
    `duration_ms` and `model` are the only fields ok/error/avoided all
    populate meaningfully; the rest degrade to None where they don't apply.
    """

    status: str
    duration_ms: int
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    unit: str | None = None
    output_chars: int | None = None


@dataclass(frozen=True)
class CallAttribution:
    """What the ambient context (telemetry/context.py) knew at the moment a
    measurement arrived. `run_id` is nullable - a call made with no open
    open_run() still gets a row (AD-11), just without a parent."""

    run_id: int | None
    purpose: str
    article_id: int | None
    attempt: int
