import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from gabay.core.llm_router import classify_intent, IntentResult
from gabay.core.config import settings

@pytest.mark.asyncio
async def test_classify_intent_local_regex():
    # Test local regex matching
    result = await classify_intent("/brief")
    assert result.intent == "brief"
    
    result = await classify_intent("/search world")
    assert result.intent == "search"
    assert result.command_args == "world"

@pytest.mark.asyncio
async def test_classify_intent_groq():
    # Mock settings
    with patch("gabay.core.llm_router.settings") as mock_settings:
        mock_settings.groq_api_key = "fake_key"
        mock_settings.llm_provider = "groq"
        
        # Mock Groq client
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"intent": "brief", "command_args": ""}'
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch("gabay.core.llm_router.AsyncGroq", return_value=mock_client):
            result = await classify_intent("give me a briefing")
            assert result.intent == "brief"
            mock_client.chat.completions.create.assert_called_once()

@pytest.mark.asyncio
async def test_classify_intent_gemini():
    # Mock settings
    with patch("gabay.core.llm_router.settings") as mock_settings:
        mock_settings.groq_api_key = "fake_groq_key" # Needs this to skip local check if isatty is false
        mock_settings.gemini_api_key = "fake_gemini_key"
        mock_settings.llm_provider = "gemini"
        
        # Mock Gemini
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = '{"intent": "search", "command_args": "stocks"}'
        mock_model.generate_content_async.return_value = mock_response
        
        with patch("gabay.core.llm_router.genai.GenerativeModel", return_value=mock_model) as mock_gen_model:
            with patch("gabay.core.llm_router.genai.configure"):
                result = await classify_intent("search for stocks")
                assert result.intent == "search"
                assert result.command_args == "stocks"
                mock_model.generate_content_async.assert_called_once()

@pytest.mark.asyncio
async def test_parse_intent_json_nested():
    from gabay.core.llm_router import _parse_intent_json
    
    # Test nested dict serialization
    json_str = '{"intent": "email", "command_args": {"action": "send", "recipient": "test@example.com"}}'
    result = _parse_intent_json(json_str)
    assert result.intent == "email"
    assert '"action": "send"' in result.command_args
    assert '"recipient": "test@example.com"' in result.command_args
