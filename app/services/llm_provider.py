"""LLM provider factory — supports OpenAI and Gemini.

Usage:
    from app.services.llm_provider import create_chat_model, create_feedback_model

    chat_llm = create_chat_model(temperature=0.7)       # fast tier
    feedback_llm = create_feedback_model(temperature=0.3)  # quality tier

The provider is selected via the `LLM_PROVIDER` env var (or Streamlit secret),
defaulting to "openai". Each tier uses a different model size:
- fast tier: gpt-4o-mini / gemini-1.5-flash — patient sim + domain classification
- quality tier: gpt-4o / gemini-1.5-pro — end-of-session feedback
"""

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
    """Quality tier: end-of-session feedback generation.

    Uses a larger model since feedback is the student-facing deliverable
    and quality matters more than latency/cost for this single call per session.
    """
    provider = get_provider_name()
    if provider == "gemini":
        return _build_gemini(settings.gemini_feedback_model, temperature)
    return _build_openai(settings.openai_feedback_model, temperature)


def supports_json_mode() -> bool:
    """Whether the current provider supports OpenAI-style `response_format` JSON mode.

    Gemini handles JSON via `response_mime_type` at construction time, not via
    a runtime `.bind()`. Callers that care can branch on this helper.
    """
    return get_provider_name() == "openai"
