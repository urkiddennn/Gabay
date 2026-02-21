import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

# Mock ALL core dependencies
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()
sys.modules["googleapiclient"] = MagicMock()
sys.modules["googleapiclient.discovery"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.credentials"] = MagicMock()
sys.modules["notion_client"] = MagicMock()
sys.modules["groq"] = MagicMock()

# Mock core submodules
sys.modules["core.config"] = MagicMock()
sys.modules["core.connectors.token_manager"] = MagicMock()
sys.modules["core.connectors.google_api"] = MagicMock()
sys.modules["core.connectors.imap_api"] = MagicMock()
sys.modules["core.connectors.meta_api"] = MagicMock()

# Add the project root to sys.path
sys.path.append(os.getcwd())

from core.skills.brief import generate_brief

async def test_generate_brief():
    print("Testing generate_brief...")
    with patch("core.skills.brief.get_unread_emails_imap") as mock_imap, \
         patch("core.skills.brief.get_unread_emails") as mock_google, \
         patch("core.skills.brief.get_unread_notifications") as mock_meta, \
         patch("core.skills.brief.AsyncGroq") as mock_groq:
        
        mock_imap.return_value = ["IMAP Email"]
        mock_google.return_value = ["Google API Email"]
        mock_meta.return_value = ["Meta Notification"]
        
        # Mock Groq response
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        # Create a mock response object
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Mocked Briefing"))]
        
        # Mock the async call
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Set settings.groq_api_key to something non-empty
        from core.config import settings
        settings.groq_api_key = "test_key"
        
        result = await generate_brief("test_user")
        print(f"Result: {result}")
        assert result == "Mocked Briefing"
        
        # Verify calls
        mock_imap.assert_called_once()
        mock_google.assert_called_once_with("test_user")
        mock_meta.assert_called_once_with("test_user")

if __name__ == "__main__":
    asyncio.run(test_generate_brief())
    print("\nBriefing test passed!")
