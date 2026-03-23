from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    database_url: str = "sqlite:///./data/nurse_llm.db"
    scenarios_dir: str = "./data/scenarios"
    max_turns: int = 30

    # LangChain conversation memory
    summary_after_turns: int = 15  # Summarize history after this many turns

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
