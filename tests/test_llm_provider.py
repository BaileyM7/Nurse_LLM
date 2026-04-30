"""Tests for app/services/llm_provider.py — provider factory and missing-key errors.

All tests patch the `settings` object directly so no real API keys are needed.
"""

from unittest.mock import MagicMock, patch

import pytest

import app.services.llm_provider as llm_provider_module
from app.services.llm_provider import (
    create_chat_model,
    create_feedback_model,
    get_provider_name,
    supports_json_mode,
)

# ---------------------------------------------------------------------------
# Missing-key error paths
# ---------------------------------------------------------------------------


def test_missing_openai_key_raises_value_error():
    """create_chat_model with openai provider and no key should raise ValueError."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "openai"
    mock_settings.openai_api_key = ""  # empty = missing
    mock_settings.openai_model_name = "gpt-4o-mini"

    with patch.object(llm_provider_module, "settings", mock_settings), pytest.raises(
        ValueError, match="OPENAI_API_KEY"
    ):
        create_chat_model(temperature=0.7)


def test_missing_gemini_key_raises_value_error():
    """create_chat_model with gemini provider and no key should raise ValueError."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "gemini"
    mock_settings.gemini_api_key = ""  # empty = missing
    mock_settings.gemini_model_name = "gemini-1.5-flash"

    # Ensure _GEMINI_AVAILABLE is True for this test
    with patch.object(llm_provider_module, "settings", mock_settings), patch.object(
        llm_provider_module, "_GEMINI_AVAILABLE", True
    ), pytest.raises(ValueError, match="GEMINI_API_KEY"):
        create_chat_model(temperature=0.7)


def test_missing_openai_feedback_key_raises_value_error():
    """create_feedback_model with openai provider and no key should raise ValueError."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "openai"
    mock_settings.openai_api_key = ""
    mock_settings.openai_feedback_model = "gpt-4o"

    with patch.object(llm_provider_module, "settings", mock_settings), pytest.raises(
        ValueError, match="OPENAI_API_KEY"
    ):
        create_feedback_model(temperature=0.3)


def test_missing_gemini_feedback_key_raises_value_error():
    """create_feedback_model with gemini provider and no key should raise ValueError."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "gemini"
    mock_settings.gemini_api_key = ""
    mock_settings.gemini_feedback_model = "gemini-1.5-pro"

    with patch.object(llm_provider_module, "settings", mock_settings), patch.object(
        llm_provider_module, "_GEMINI_AVAILABLE", True
    ), pytest.raises(ValueError, match="GEMINI_API_KEY"):
        create_feedback_model(temperature=0.3)


# ---------------------------------------------------------------------------
# get_provider_name
# ---------------------------------------------------------------------------


def test_get_provider_name_openai():
    mock_settings = MagicMock()
    mock_settings.llm_provider = "openai"
    with patch.object(llm_provider_module, "settings", mock_settings):
        assert get_provider_name() == "openai"


def test_get_provider_name_gemini():
    mock_settings = MagicMock()
    mock_settings.llm_provider = "gemini"
    with patch.object(llm_provider_module, "settings", mock_settings):
        assert get_provider_name() == "gemini"


def test_get_provider_name_invalid_raises():
    """An unrecognized provider name should raise ValueError."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "anthropic"
    with patch.object(llm_provider_module, "settings", mock_settings), pytest.raises(
        ValueError, match="LLM_PROVIDER"
    ):
        get_provider_name()


def test_get_provider_name_whitespace_stripped():
    """Leading/trailing whitespace in provider name should be normalized."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "  openai  "
    with patch.object(llm_provider_module, "settings", mock_settings):
        assert get_provider_name() == "openai"


# ---------------------------------------------------------------------------
# supports_json_mode
# ---------------------------------------------------------------------------


def test_supports_json_mode_true_for_openai():
    mock_settings = MagicMock()
    mock_settings.llm_provider = "openai"
    with patch.object(llm_provider_module, "settings", mock_settings):
        assert supports_json_mode() is True


def test_supports_json_mode_false_for_gemini():
    mock_settings = MagicMock()
    mock_settings.llm_provider = "gemini"
    with patch.object(llm_provider_module, "settings", mock_settings):
        assert supports_json_mode() is False


# ---------------------------------------------------------------------------
# Gemini unavailable path
# ---------------------------------------------------------------------------


def test_gemini_unavailable_raises_import_error():
    """If langchain-google-genai is not installed, creating a gemini model raises ImportError."""
    mock_settings = MagicMock()
    mock_settings.llm_provider = "gemini"
    mock_settings.gemini_api_key = "fake-key"
    mock_settings.gemini_model_name = "gemini-1.5-flash"

    with patch.object(llm_provider_module, "settings", mock_settings), patch.object(
        llm_provider_module, "_GEMINI_AVAILABLE", False
    ), pytest.raises(ImportError, match="langchain-google-genai"):
        create_chat_model(temperature=0.7)
