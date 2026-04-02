from pydantic_settings import BaseSettings
from pathlib import Path

# Resolve repo root so relative paths work regardless of working directory
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _get_streamlit_secret(key: str, default: str = "") -> str:
    """Try to read a secret from Streamlit secrets (for Streamlit Cloud)."""
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


# Determine .env path — may not exist on Streamlit Cloud
_env_file = _REPO_ROOT / ".env"
_env_path = str(_env_file) if _env_file.exists() else None


class Settings(BaseSettings):
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    database_url: str = f"sqlite:///{_REPO_ROOT / 'data' / 'nurse_llm.db'}"
    scenarios_dir: str = str(_REPO_ROOT / "data" / "scenarios")
    max_turns: int = 30

    # LangChain conversation memory
    summary_after_turns: int = 15  # Summarize history after this many turns

    model_config = {"env_file": _env_path, "env_file_encoding": "utf-8"}


settings = Settings()

# Override with Streamlit secrets if available (for Streamlit Cloud deployment)
_st_key = _get_streamlit_secret("OPENAI_API_KEY")
if _st_key:
    settings.openai_api_key = _st_key
