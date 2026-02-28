import json
import logging
from pathlib import Path
from gabay.core.config import settings

logger = logging.getLogger(__name__)

class TokenManager:
    def __init__(self):
        self.secrets_dir = Path(settings.data_dir) / "secrets"
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
        self.tokens_file = self.secrets_dir / "tokens.json"
        if not self.tokens_file.exists():
            with open(self.tokens_file, "w") as f:
                json.dump({}, f)

    def _read_tokens(self) -> dict:
        with open(self.tokens_file, "r") as f:
            return json.load(f)

    def _write_tokens(self, data: dict):
        with open(self.tokens_file, "w") as f:
            json.dump(data, f, indent=4)

    def save_token(self, provider: str, user_id: str, token_data: dict):
        """
        Save OAuth tokens for a specific provider and user.
        """
        data = self._read_tokens()
        if user_id not in data:
            data[user_id] = {}
        data[user_id][provider] = token_data
        self._write_tokens(data)
        logger.info(f"Saved token for {provider} (user: {user_id})")

    def get_token(self, provider: str, user_id: str) -> dict:
        data = self._read_tokens()
        return data.get(str(user_id), {}).get(provider)

    def get_all_users(self) -> list:
        """Returns all user IDs that have at least one token stored."""
        data = self._read_tokens()
        return list(data.keys())

token_manager = TokenManager()
