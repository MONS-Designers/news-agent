from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEWSAGENT_", extra="ignore")

    database_url: str = "sqlite:///./newsagent.db"

    # Which LLM provider adapter the pipeline uses (see newsagent.llm.factory)
    llm_provider: str = "mock"

    # Which Suggestion Source adapter the profile picker uses (see
    # newsagent.suggestions.factory) — independent of llm_provider (AD-3).
    suggestion_provider: str = "popularity"

    # Relevance verdict threshold (0.7 = the contract's "clearly on-topic" anchor)
    relevance_threshold: float = 0.7

    # Weighted digest ranking (issue #25): final_score = relevance_weight*relevance
    # + recency_weight*recency + interest_weight*interest. Weight trio sums to 1.0.
    relevance_weight: float = 0.40
    recency_weight: float = 0.25
    interest_weight: float = 0.35
    # interest = interestingness_weight*llm_interestingness + personalization_weight*affinity.
    interestingness_weight: float = 0.60
    personalization_weight: float = 0.40
    # Recency decay half-life: an article this many hours old scores half of a
    # brand-new one. Tuned to the weekly send cadence — 84h (half a week) keeps
    # a Monday article competitive against a Sunday one instead of burying it.
    recency_half_life_hours: float = 84.0
    # Top-N articles selected per user's digest per run; the rest stay undelivered.
    digest_max_articles: int = 7

    # Which email sender adapter the pipeline uses (see newsagent.mail.factory)
    email_sender: str = "console"
    # When set, the console sender also writes each email's HTML here
    email_outbox_dir: str = ""

    # SMTP sender (email_sender="smtp") — real delivery, no vendor SDK.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    smtp_use_tls: bool = True
    # Where log records go (see newsagent.logging_setup): stderr | stdout | file.
    # The defaults reproduce Python's last-resort behavior — WARNING+ to stderr.
    log_destination: str = "stderr"
    log_level: str = "WARNING"
    # Required when log_destination="file"; ignored otherwise.
    log_file: str = ""

    # Self-registration hard cap (FR2) — total User rows, admin-seeded or
    # self-registered. Enforced atomically at the DB level (FR3), not by an
    # application-level count check.
    max_users: int = 10

    # Google OAuth (set real values in .env — never commit them)
    google_client_id: str = ""
    google_client_secret: str = ""
    # Secret for signing the session cookie; override in .env for anything non-local.
    session_secret: str = ""
    # Where the API redirects back to after login (the Vue dev server).
    frontend_url: str = "http://127.0.0.1:5173"
    # Publicly reachable base URL of this API — used to build the open-tracking
    # pixel URL embedded in outgoing digest emails.
    backend_base_url: str = "http://127.0.0.1:8000"

    # External LLM (llm_provider="external", articles) — unprefixed, shared
    # with no other adapter.
    external_llm_base_url: str = Field(default="", alias="EXTERNAL_LLM_BASE_URL")
    external_llm_auth_token: str = Field(default="", alias="EXTERNAL_LLM_AUTH_TOKEN")
    external_llm_model: str = Field(default="", alias="EXTERNAL_LLM_MODEL")

    # Local LLM (suggestion_provider="llm", profile suggestions) — unprefixed,
    # deliberately separate config from external_llm_* (AD-3).
    local_llm_base_url: str = Field(default="", alias="LOCAL_LLM_BASE_URL")
    local_llm_auth_token: str = Field(default="", alias="LOCAL_LLM_AUTH_TOKEN")
    local_llm_model: str = Field(default="", alias="LOCAL_LLM_MODEL")


settings = Settings()
