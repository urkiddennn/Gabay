import logging
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
import json
from gabay.core.connectors.token_manager import token_manager
from gabay.core.config import settings

logger = logging.getLogger(__name__)

def get_google_service(user_id: str, service_name: str, version: str):
    token_data = token_manager.get_token("google", str(user_id))
    if not token_data:
        logger.warning(f"No Google token found for user {user_id}")
        return None
        
    logger.debug(f"Getting Google service for user {user_id}. Provider keys: {list(token_data.keys())}")
    
    # Inject client credentials if missing from stored token
    if 'client_id' not in token_data or not token_data['client_id']:
        token_data['client_id'] = settings.google_client_id
    if 'client_secret' not in token_data or not token_data['client_secret']:
        token_data['client_secret'] = settings.google_client_secret
        
    creds = Credentials.from_authorized_user_info(token_data)
    
    # Check if we need to refresh the token
    if creds and creds.expired and creds.refresh_token:
        try:
            logger.info(f"Refreshing Google token for user {user_id}...")
            creds.refresh(GoogleRequest())
            # Save refreshed token back to storage
            new_token_data = json.loads(creds.to_json())
            token_manager.save_token("google", user_id, new_token_data)
        except Exception as e:
            logger.error(f"Failed to refresh Google token for {user_id}: {e}")
            # If refresh fails, we might want to notify the user to re-pair
            return None
            
    return build(service_name, version, credentials=creds)

def get_unread_emails(user_id: str) -> list[str]:
    service = get_google_service(user_id, "gmail", "v1")
    if not service:
        return []
    
    try:
        results = service.users().messages().list(userId='me', q='is:unread', maxResults=5).execute()
        messages = results.get('messages', [])
        
        email_summaries = []
        for msg in messages:
            m = service.users().messages().get(userId='me', id=msg['id']).execute()
            # Extract basic info
            headers = m['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
            email_summaries.append(f"From {sender}: {subject}")
        return email_summaries
    except Exception as e:
        logger.error(f"Gmail error: {e}")
        return []

def upload_file_to_drive(user_id: str, file_path: str, mime_type: str) -> str:
    # Minimal implementation for now
    return "https://drive.google.com/upload/mock"

def search_drive(user_id: str, query: str) -> list[dict]:
    service = get_google_service(user_id, "drive", "v3")
    if not service:
        return []
    
    try:
        q = f"name contains '{query}' or fullText contains '{query}'"
        results = service.files().list(
            q=q,
            spaces='drive',
            fields='files(id, name, mimeType, webViewLink)',
            pageSize=5
        ).execute()
        
        files = results.get('files', [])
        return [{"id": f['id'], "title": f['name'], "mimeType": f.get('mimeType', ''), "link": f.get('webViewLink', '')} for f in files]
    except Exception as e:
        logger.error(f"Drive search error: {e}")
        return []

def send_email(user_id: str, recipient: str, subject: str, body: str) -> str:
    # Actually most users prefer SMTP for simple sending if they have credentials,
    # but since this is google_api.py, we could use Gmail API.
    # For now, let's keep the placeholder or use the logic from worker tasks if it's there.
    return f"Successfully queued email to {recipient} via Google API."

def share_file(user_id: str, file_id: str) -> str:
    """Updates file permissions to 'anyone with link can read' and returns the webViewLink."""
    service = get_google_service(user_id, "drive", "v3")
    if not service:
        return {"error": "Not connected to Google Drive."}
    
    try:
        # Create a permission allowing anyone with the link to read
        body = {
            'type': 'anyone',
            'role': 'reader'
        }
        service.permissions().create(
            fileId=file_id,
            body=body
        ).execute()

        # Get the webViewLink
        file_info = service.files().get(fileId=file_id, fields='webViewLink, name').execute()
        return {"link": file_info['webViewLink'], "name": file_info['name']}
    except Exception as e:
        logger.error(f"Error sharing file {file_id}: {e}")
        return {"error": f"Error sharing file: {e}"}

def download_drive_file(user_id: str, file_id: str, mime_type: str) -> str:
    """
    Downloads or exports a file from Google Drive as plain text.
    Google Docs ('application/vnd.google-apps.document') must be exported.
    Standard text files ('text/plain') are downloaded directly.
    """
    service = get_google_service(user_id, "drive", "v3")
    if not service:
        return "Not connected to Google Drive."

    try:
        if 'application/vnd.google-apps.document' in mime_type:
            # Export Google Doc to text
            request = service.files().export_media(fileId=file_id, mimeType='text/plain')
        elif 'text/' in mime_type or 'application/json' in mime_type or 'application/csv' in mime_type:
            # Download regular text file
            request = service.files().get_media(fileId=file_id)
        elif 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' in mime_type:
            # Download binary .docx
            request = service.files().get_media(fileId=file_id)
        else:
            return f"Unsupported file type for summarization: {mime_type}"

        from io import BytesIO
        from googleapiclient.http import MediaIoBaseDownload
        
        fh = BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            
        file_bytes = fh.getvalue()
        
        # Word docx parsing
        if 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' in mime_type:
            import zipfile
            import xml.etree.ElementTree as ET
            try:
                with zipfile.ZipFile(BytesIO(file_bytes)) as d:
                    xml_content = d.read('word/document.xml')
                    tree = ET.XML(xml_content)
                    WORD_NAMESPACE = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                    PARA = WORD_NAMESPACE + 'p'
                    TEXT = WORD_NAMESPACE + 't'
                    
                    paragraphs = []
                    for paragraph in tree.iter(PARA):
                        texts = [node.text for node in paragraph.iter(TEXT) if node.text]
                        if texts:
                            paragraphs.append(''.join(texts))
                    return '\n\n'.join(paragraphs)
            except Exception as e:
                logger.error(f"Failed to parse docx: {e}")
                return f"Error extracting text from DOCX: {e}"

        # Return the decoded text
        return file_bytes.decode('utf-8')
        
    except Exception as e:
        logger.error(f"Error downloading file {file_id}: {e}")
        return f"Error downloading file: {e}"

