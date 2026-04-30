"""Provider factory for OpenAI and Gemini; fast tier for chat, quality tier for feedback."""

from langchain_openai import ChatOpenAI

from app.config import settings

# Lazy-import Gemini so the openai-only install path still works if
# langchain-google-genai is absent.
try:
    from langchain_google_genai import ChatGoogleGenerativeAI

    _GEMINI_AVAILABLE = True
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore[assignment]
    _GEMINI_AVAILABLE = False


def get_provider_name() -> str:
    provider = (settings.llm_provider or "openai").strip().lower()
    if provider not in {"openai", "gemini"}:
        raise ValueError(
            f"LLM_PROVIDER must be 'openai' or 'gemini', got: {provider!r}"
        )
    return provider


def _build_openai(model: str, temperature: float):
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and set the key, "
            "or set LLM_PROVIDER=gemini and GEMINI_API_KEY to use Gemini instead."
        )
    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key,
        temperature=temperature,
    )


def _build_gemini(model: str, temperature: float):
    if not _GEMINI_AVAILABLE:
        raise ImportError(
            "langchain-google-genai is not installed. "
            "Run: pip install langchain-google-genai"
        )
    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and set the key, "
            "or set LLM_PROVIDER=openai and OPENAI_API_KEY to use OpenAI instead."
        )
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.gemini_api_key,
        temperature=temperature,
    )


def create_chat_model(temperature: float):
    """Fast tier: patient simulation and domain classification."""
    provider = get_provider_name()
    if provider == "gemini":
        return _build_gemini(settings.gemini_model_name, temperature)
    return _build_openai(settings.openai_model_name, temperature)


def create_feedback_model(temperature: float):
    """Quality tier: end-of-session feedback (one call per session, bigger model)."""
    provider = get_provider_name()
    if provider == "gemini":
        return _build_gemini(settings.gemini_feedback_model, temperature)
    return _build_openai(settings.openai_feedback_model, temperature)


def supports_json_mode() -> bool:
    """True for OpenAI; Gemini uses response_mime_type at construction instead."""
    return get_provider_name() == "openai"
