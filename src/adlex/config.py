from functools import lru_cache

from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ADLEX_", extra="ignore")

    env: str = "local"

    database_url: PostgresDsn
    redis_url: str = "redis://localhost:6379/0"

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: SecretStr
    llm_proxy: str = ""
    model_main: str = "qwen/qwen3.8-flash"
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 3

    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dim: int = 768
    retrieve_top_k: int = 20
    rerank_top_n: int = 4
    agent_max_steps: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
