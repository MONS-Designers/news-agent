from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEWSAGENT_", extra="ignore")

    database_url: str = "sqlite:///./newsagent.db"

    # Which LLM provider adapter the pipeline uses (see newsagent.llm.factory)
    llm_provider: str = "mock"

    # Relevance verdict threshold (0.7 = the contract's "clearly on-topic" anchor)
    relevance_threshold: float = 0.7

    # Which email sender adapter the pipeline uses (see newsagent.mail.factory)
    email_sender: str = "console"
    # When set, the console sender also writes each email's HTML here
    email_outbox_dir: str = ""

    # Google OAuth (set real values in .env — never commit them)
    google_client_id: str = ""
    google_client_secret: str = ""
    # Secret for signing the session cookie; override in .env for anything non-local.
    session_secret: str = ""
    # Where the API redirects back to after login (the Vue dev server).
    frontend_url: str = "http://127.0.0.1:5173"


settings = Settings()
