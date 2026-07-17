from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEWSAGENT_", extra="ignore")

    database_url: str = "sqlite:///./newsagent.db"


settings = Settings()
