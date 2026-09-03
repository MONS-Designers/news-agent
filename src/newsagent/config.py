from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEWSAGENT_", extra="ignore")

    database_url: str = "postgresql+psycopg://user:password@host/dbname"

    # Which LLM provider adapter the pipeline uses (see newsagent.llm.factory)
    llm_provider: str = "mock"

    # Which Suggestion Source adapter the profile picker uses (see
    # newsagent.suggestions.factory) - independent of llm_provider (AD-3).
    suggestion_provider: str = "popularity"

    # Relevance verdict threshold (0.7 = the contract's "clearly on-topic" anchor)
    relevance_threshold: float = 0.7

    # Bounded retries before a failing article's summary_status becomes the
    # terminal "failed" (Epic C, Story C.1). Matches LLMProvider's own internal
    # retry default (newsagent.llm.base) - consistency, not a separate tuning.
    max_summarize_attempts: int = 3

    # Bounded retries before a failing article's extraction_status becomes the
    # terminal "failed" (Epic D, Story D.1) - same pattern as C.1 above.
    max_extraction_attempts: int = 2
    # Extracted full_text is truncated to this length before it's ever stored,
    # so it's already bounded before it could reach an LLM prompt (NFR3).
    extraction_max_chars: int = 10_000
    # Polite, bounded fetching (Epic D, Story D.2) - a slow/unresponsive source
    # can't stall the run, and a bounded worker pool can't hammer many sources
    # at once or look like a scraper.
    extraction_timeout_seconds: float = 10.0
    extraction_concurrency: int = 5
    extraction_user_agent: str = "NewsAgent/1.0 (+https://github.com/MONS-Designers/news-agent)"

    # Bounded worker pools for the other network-bound stages, same reasoning
    # as extraction_concurrency above: overlap I/O-bound calls instead of
    # paying for them back-to-back, without unboundedly hammering RSS hosts
    # or the LLM provider's own rate limit.
    fetch_concurrency: int = 5
    filter_concurrency: int = 5
    summarize_concurrency: int = 5

    # Weighted digest ranking (issue #25): final_score = relevance_weight*relevance
    # + recency_weight*recency + interest_weight*interest. Weight trio sums to 1.0.
    relevance_weight: float = 0.40
    recency_weight: float = 0.25
    interest_weight: float = 0.35
    # interest = interestingness_weight*llm_interestingness + personalization_weight*affinity.
    interestingness_weight: float = 0.60
    personalization_weight: float = 0.40
    # Recency decay half-life: an article this many hours old scores half of a
    # brand-new one. Tuned to the weekly send cadence - 84h (half a week) keeps
    # a Monday article competitive against a Sunday one instead of burying it.
    recency_half_life_hours: float = 84.0
    # Top-N articles selected per user's digest per run; the rest stay undelivered.
    digest_max_articles: int = 7

    # LOCAL DEVELOPMENT ONLY. When set to an email address, the API exposes
    # GET /auth/dev-login, which signs that identity in without Google. Empty
    # (the default) means the route is never registered at all - not a
    # disabled route that 404s on a flag, but no route, so a stray value in a
    # production environment cannot re-enable it by accident.
    dev_auth_email: str = ""

    # Which email sender adapter the pipeline uses (see newsagent.mail.factory)
    email_sender: str = "console"
    # When set, the console sender also writes each email's HTML here
    email_outbox_dir: str = ""

    # SMTP sender (email_sender="smtp") - real delivery, no vendor SDK.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    smtp_use_tls: bool = True
    # Verbosity for the DB-backed log handler (see newsagent.logging_setup).
    # Every record is always written to the DB - there is no destination choice.
    log_level: str = "WARNING"

    # Self-registration hard cap (FR2) - total User rows, admin-seeded or
    # self-registered. Enforced atomically at the DB level (FR3), not by an
    # application-level count check.
    max_users: int = 10

    # Google OAuth (set real values in .env - never commit them)
    google_client_id: str = ""
    google_client_secret: str = ""
    # Secret for signing the session cookie; override in .env for anything non-local.
    session_secret: str = ""
    # Session cookie's Set-Cookie Domain attribute. Empty (default) = host-only,
    # correct for local dev and single-domain deploys. Set to a parent domain
    # (e.g. ".newsagent-ai.com") only when frontend and backend are split across
    # subdomains, so the cookie set by the backend is sent on requests to both.
    session_cookie_domain: str = ""
    # Where the API redirects back to after login (the Vue dev server).
    frontend_url: str = "http://127.0.0.1:5173"
    # Publicly reachable base URL of this API - used to build the open-tracking
    # pixel URL embedded in outgoing digest emails.
    backend_base_url: str = "http://127.0.0.1:8000"

    # External LLM (llm_provider="external", articles) - unprefixed, shared
    # with no other adapter.
    external_llm_base_url: str = Field(default="", alias="EXTERNAL_LLM_BASE_URL")
    external_llm_auth_token: str = Field(default="", alias="EXTERNAL_LLM_AUTH_TOKEN")
    external_llm_model: str = Field(default="", alias="EXTERNAL_LLM_MODEL")

    # Local LLM (suggestion_provider="llm", profile suggestions) - unprefixed,
    # deliberately separate config from external_llm_* (AD-3).
    local_llm_base_url: str = Field(default="", alias="LOCAL_LLM_BASE_URL")
    local_llm_auth_token: str = Field(default="", alias="LOCAL_LLM_AUTH_TOKEN")
    local_llm_model: str = Field(default="", alias="LOCAL_LLM_MODEL")


settings = Settings()
