import logging
import mimetypes
from gabay.core.connectors.google_api import upload_file_to_drive
from gabay.core.connectors.notion_api import append_to_database

logger = logging.getLogger(__name__)

def save_file_or_text(user_id: str, file_path: str = None, text_content: str = None) -> str:
    """
    Determines if the payload is a file or text.
    Files are uploaded to Google Drive.
    Text notes are appended to a Notion database.
    """
    try:
        if file_path:
            # Guess mime type to determine upload strategy
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type.startswith("text"):
                # E.g. save as text to Notion
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                url = append_to_database(user_id, content)
                return f"Text file saved to Notion database: {url}"
            else:
                # Media or binary -> Drive
                url = upload_file_to_drive(user_id, file_path, mime_type or "application/octet-stream")
                return f"File uploaded to Google Drive Gabay folder: {url}"
                
        elif text_content:
            url = append_to_database(user_id, text_content)
            return f"Note saved to Notion database: {url}"
            
        else:
            return "Nothing to save."
    except Exception as e:
        logger.error(f"Error in save_file_or_text: {e}")
        return f"Failed to save: {str(e)}"
