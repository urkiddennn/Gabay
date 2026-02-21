import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Mock ALL core dependencies to avoid ModuleNotFoundError and other initialization issues
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()
sys.modules["googleapiclient"] = MagicMock()
sys.modules["googleapiclient.discovery"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.credentials"] = MagicMock()
sys.modules["notion_client"] = MagicMock()
sys.modules["groq"] = MagicMock()

# Mock core submodules that are not needed for this skill test
sys.modules["core.config"] = MagicMock()
sys.modules["core.connectors.token_manager"] = MagicMock()
sys.modules["core.connectors.google_api"] = MagicMock()
sys.modules["core.connectors.notion_api"] = MagicMock()

# Now we can import the skill
# We need to manually inject the mocks into the skill module's namespace if they were already imported
# but since we are mocking sys.modules before import, it should work.

# Add the project root to sys.path
sys.path.append(os.getcwd())

from core.skills.read import handle_read_skill

async def test_read_all():
    print("Testing read all...")
    # These functions are imported from the mocked modules above
    with patch("core.skills.read.get_unread_emails") as mock_emails, \
         patch("core.skills.read.search_notion") as mock_notion:
        
        mock_emails.return_value = ["Email 1", "Email 2"]
        mock_notion.return_value = [{"title": "Page 1", "link": "http://notion.so/1"}]
        
        result = await handle_read_skill("test_user", "all")
        print(f"Result:\n{result}")
        assert "Gmail" in result
        assert "Notion" in result
        assert "Email 1" in result
        assert "Page 1" in result

async def test_read_gmail_only():
    print("\nTesting read gmail only...")
    with patch("core.skills.read.get_unread_emails") as mock_emails, \
         patch("core.skills.read.search_notion") as mock_notion:
        
        mock_emails.return_value = ["Email 1"]
        mock_notion.return_value = [{"title": "Page 1", "link": "http://notion.so/1"}]
        
        result = await handle_read_skill("test_user", "gmail")
        print(f"Result:\n{result}")
        assert "Gmail" in result
        assert "Notion" not in result

async def test_read_empty():
    print("\nTesting read empty...")
    with patch("core.skills.read.get_unread_emails") as mock_emails, \
         patch("core.skills.read.search_notion") as mock_notion:
        
        mock_emails.return_value = []
        mock_notion.return_value = []
        
        result = await handle_read_skill("test_user", "all")
        print(f"Result:\n{result}")
        assert "I couldn't find anything new" in result

if __name__ == "__main__":
    asyncio.run(test_read_all())
    asyncio.run(test_read_gmail_only())
    asyncio.run(test_read_empty())
    print("\nAll tests passed!")
