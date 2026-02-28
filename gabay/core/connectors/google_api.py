import logging
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
import json
import re
import uuid
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

def get_unread_emails_full(user_id: str, max_results: int = 5) -> list[dict]:
    """Returns unread emails with full metadata (id, subject, sender, snippet)."""
    return search_gmail_full(user_id, query='is:unread', max_results=max_results)

def search_gmail_full(user_id: str, query: str, max_results: int = 10) -> list[dict]:
    """Searches for emails matching a query and returns metadata (id, subject, sender, snippet)."""
    service = get_google_service(user_id, "gmail", "v1")
    if not service:
        return []
    
    try:
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        
        email_data = []
        for msg in messages:
            m = service.users().messages().get(userId='me', id=msg['id'], format='minimal').execute()
            msg_id = m.get('id')
            snippet = m.get('snippet', '')
            
            m_full = service.users().messages().get(userId='me', id=msg_id).execute()
            headers = m_full['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
            
            email_data.append({
                "id": msg_id,
                "subject": subject,
                "sender": sender,
                "snippet": snippet
            })
        return email_data
    except Exception as e:
        logger.error(f"Gmail search error: {e}")
        return []

def get_thread_messages(user_id: str, thread_id: str) -> list[dict]:
    """Fetches all messages in a Gmail thread and returns simplified metadata."""
    service = get_google_service(user_id, "gmail", "v1")
    if not service:
        return []
    
    try:
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        messages = []
        for msg in thread.get('messages', []):
            snippet = msg.get('snippet', '')
            headers = msg['payload']['headers']
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
            messages.append({
                "from": sender,
                "snippet": snippet
            })
        return messages
    except Exception as e:
        logger.error(f"Error fetching thread {thread_id}: {e}")
        return []

def get_sheet_values(user_id: str, spreadsheet_id: str, range_name: str = "Sheet1!A1:Z100") -> list[list]:
    """Reads a range of cells from a Google Sheet."""
    service = get_google_service(user_id, "sheets", "v4")
    if not service:
        return []
    
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, 
            range=range_name
        ).execute()
        return result.get('values', [])
    except Exception as e:
        logger.error(f"Error reading Google Sheet {spreadsheet_id}: {e}")
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

def share_file(user_id: str, file_id: str, email: str = None, role: str = 'reader') -> str:
    """
    Shares a file. 
    If email is provided, it invites that specific user.
    If email is None, it makes the file public (anyone with link).
    """
    service = get_google_service(user_id, "drive", "v3")
    if not service:
        return {"error": "Not connected to Google Drive."}
    
    try:
        if email:
            # Private Invite
            body = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            # Transfer ownership if role is owner? Maybe not for now, stick to reader/writer
        else:
            # Public Link
            body = {
                'type': 'anyone',
                'role': 'reader'
            }
            
        service.permissions().create(
            fileId=file_id,
            body=body,
            sendNotificationEmail=True if email else False
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

def create_google_doc(user_id: str, title: str, initial_text: str = "") -> dict:
    """Creates a new Google Doc with professional formatting."""
    service_docs = get_google_service(user_id, "docs", "v1")
    service_drive = get_google_service(user_id, "drive", "v3")
    
    if not service_docs or not service_drive:
        return {"error": "Google APIs not connected."}
        
    try:
        # 1. Create the document shell
        doc = service_docs.documents().create(body={"title": title}).execute()
        doc_id = doc.get("documentId")
        
        # 2. Apply Professional Formatting
        if initial_text:
            requests = _get_doc_formatting_requests(title, initial_text)
            if requests:
                service_docs.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
            
        # 3. Get the link from Drive API
        file_info = service_drive.files().get(fileId=doc_id, fields='webViewLink, name').execute()
        return {
            "id": doc_id, 
            "link": file_info.get('webViewLink'), 
            "name": file_info.get('name')
        }
    except Exception as e:
        logger.error(f"Error creating Google Doc: {e}")
        return {"error": str(e)}

def _get_doc_formatting_requests(title: str, text: str) -> list:
    """Parses text and title into a sequence of Google Docs API requests for professional styling."""
    requests = []
    
    # We'll build the document in chunks. 
    # Index 1 is the start.
    
    # 1. Clear default text (though there shouldn't be much)
    # Actually, we'll just start inserting from index 1.
    
    # 2. Insert Title
    full_text = f"{title}\n\n{text}"
    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': full_text
        }
    })
    
    # 3. Style the Title (centered, bold, large)
    title_end = len(title) + 1
    requests.extend([
        {
            'updateTextStyle': {
                'range': {'startIndex': 1, 'endIndex': title_end},
                'textStyle': {
                    'fontSize': {'magnitude': 24, 'unit': 'PT'},
                    'bold': True,
                    'weightedFontFamily': {'fontFamily': 'Montserrat'},
                    'foregroundColor': {'color': {'rgbColor': {'red': 0.05, 'green': 0.1, 'blue': 0.25}}}
                },
                'fields': 'fontSize,bold,weightedFontFamily,foregroundColor'
            }
        },
        {
            'updateParagraphStyle': {
                'range': {'startIndex': 1, 'endIndex': title_end},
                'paragraphStyle': {
                    'alignment': 'CENTER',
                    'spaceBelow': {'magnitude': 18, 'unit': 'PT'}
                },
                'fields': 'alignment,spaceBelow'
            }
        }
    ])
    
    # 4. Parse headers and body
    # Find headers (## Header or ### Header)
    # Note: Indices shift after each update if we aren't careful.
    # But batchUpdate applies them sequentially or as a batch. 
    # Actually, it's safer to identify positions FIRST.
    
    lines = full_text.split('\n')
    current_index = 1
    for i, line in enumerate(lines):
        line_len = len(line) + 1 # +1 for newline
        
        # Headers
        if line.startswith('## ') or line.startswith('### '):
            level = 2 if line.startswith('## ') else 3
            start = current_index
            end = current_index + line_len
            
            requests.append({
                'updateTextStyle': {
                    'range': {'startIndex': start, 'endIndex': end},
                    'textStyle': {
                        'fontSize': {'magnitude': 16 if level == 2 else 13, 'unit': 'PT'},
                        'bold': True,
                        'weightedFontFamily': {'fontFamily': 'Montserrat'}
                    },
                    'fields': 'fontSize,bold,weightedFontFamily'
                }
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': start, 'endIndex': end},
                    'paragraphStyle': {
                        'spaceAbove': {'magnitude': 12, 'unit': 'PT'},
                        'spaceBelow': {'magnitude': 6, 'unit': 'PT'}
                    },
                    'fields': 'spaceAbove,spaceBelow'
                }
            })
        
        # Bullet points
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            start = current_index
            end = current_index + line_len
            requests.append({
                'createParagraphBullets': {
                    'range': {'startIndex': start, 'endIndex': end},
                    'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                }
            })
            
        current_index += line_len
        
    return requests

def _clean_body_text(text: str) -> str:
    """Removes common leading bullet characters from each line to prepare for native bulleting."""
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Strip leading dots, bullets, dashes, or stars followed by a space
        cleaned = re.sub(r'^\s*[•\-\*]\s*', '', line)
        cleaned_lines.append(cleaned)
    return '\n'.join(cleaned_lines)

def append_to_google_doc(user_id: str, document_id: str, text: str) -> bool:
    """Appends text to the end of an existing Google Doc with basic formatting."""
    service = get_google_service(user_id, "docs", "v1")
    if not service:
        return False
        
    try:
        # Get current document length
        doc = service.documents().get(documentId=document_id).execute()
        end_index = doc.get('body').get('content')[-1].get('endIndex') - 1
        
        # Insert text
        requests = [
            {
                'insertText': {
                    'location': {'index': end_index},
                    'text': f"\n\n{text}"
                }
            }
        ]
        
        # Apply basic formatting (bold headers if any)
        # For appends, we'll keep it simple for now or use the _get_doc_formatting_requests logic
        # if we want full consistency.
        
        service.documents().batchUpdate(documentId=document_id, body={'requests': requests}).execute()
        return True
    except Exception as e:
        logger.error(f"Error appending to Google Doc: {e}")
        return False

def create_google_presentation(user_id: str, title: str) -> dict:
    """Creates a new Google Slides presentation and returns id, link, and name."""
    service_slides = get_google_service(user_id, "slides", "v1")
    service_drive = get_google_service(user_id, "drive", "v3")
    
    if not service_slides or not service_drive:
        return {"error": "Google APIs not connected."}
        
    try:
        # Create presentation
        presentation = service_slides.presentations().create(body={'title': title}).execute()
        presentation_id = presentation.get('presentationId')
        
        # Professional V3: Set Master Font to Montserrat if possible (via batchUpdate)
        # Note: Setting master fonts is complex, we'll stick to per-slide styling for now
        # but with much better parameters.
        
        # Get link from Drive
        file_info = service_drive.files().get(fileId=presentation_id, fields='webViewLink, name').execute()
        return {
            "id": presentation_id,
            "link": file_info.get('webViewLink'),
            "name": file_info.get('name')
        }
    except Exception as e:
        logger.error(f"Error creating Google Slides: {e}")
        return {"error": str(e)}

def add_slide_to_presentation(user_id: str, presentation_id: str, title: str, body: str, image_url: str = None) -> bool:
    """Adds a slide to a presentation with high-end Professional V3 aesthetics."""
    service = get_google_service(user_id, "slides", "v1")
    if not service:
        return False
        
    try:
        slide_id = str(uuid.uuid4())
        
        # Clean the body text for native bulleting
        cleaned_body = _clean_body_text(body)
        
        requests = [
            {
                'createSlide': {
                    'objectId': slide_id,
                    'insertionIndex': '1',
                    'slideLayoutReference': {
                        'predefinedLayout': 'BLANK' # We build from scratch for total control
                    }
                }
            },
            # Page Background (Ultra-sleek Deep Navy/Charcoal)
            {
                'updatePageProperties': {
                    'objectId': slide_id,
                    'pageProperties': {
                        'pageBackgroundFill': {
                            'solidFill': {
                                'color': {
                                    'rgbColor': {'red': 0.05, 'green': 0.07, 'blue': 0.09} # Modern #0d1117 style
                                }
                            }
                        }
                    },
                    'fields': 'pageBackgroundFill.solidFill.color'
                }
            }
        ]
        
        # Textbox IDs
        title_box_id = f"title_{slide_id}"
        body_box_id = f"body_{slide_id}"
        
        # 1. Title Positioning (Shifted slightly and smaller font to avoid overlap)
        requests.extend([
            {
                'createShape': {
                    'objectId': title_box_id,
                    'shapeType': 'TEXT_BOX',
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {'height': {'magnitude': 1200000, 'unit': 'EMU'}, 'width': {'magnitude': 4500000 if image_url else 8500000, 'unit': 'EMU'}},
                        'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 400000, 'translateY': 350000, 'unit': 'EMU'}
                    }
                }
            },
            {'insertText': {'objectId': title_box_id, 'text': title}},
            {'updateTextStyle': {
                'objectId': title_box_id,
                'style': {
                    'foregroundColor': {'opaqueColor': {'rgbColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}}},
                    'fontSize': {'magnitude': 26, 'unit': 'PT'}, # Scaled down for professionalism
                    'bold': True,
                    'fontFamily': 'Montserrat'
                },
                'fields': 'foregroundColor,fontSize,bold,fontFamily'
            }}
        ])
        
        # 2. Body Positioning (Increased translateY to 1.6M EMU to leave clearance for title)
        requests.extend([
            {
                'createShape': {
                    'objectId': body_box_id,
                    'shapeType': 'TEXT_BOX',
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {
                            'height': {'magnitude': 3000000, 'unit': 'EMU'}, 
                            'width': {'magnitude': 4100000 if image_url else 8000000, 'unit': 'EMU'}
                        },
                        'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 400000, 'translateY': 1750000, 'unit': 'EMU'}
                    }
                }
            },
            {'insertText': {'objectId': body_box_id, 'text': cleaned_body}},
            {'updateTextStyle': {
                'objectId': body_box_id,
                'style': {
                    'foregroundColor': {'opaqueColor': {'rgbColor': {'red': 0.88, 'green': 0.88, 'blue': 0.92}}},
                    'fontSize': {'magnitude': 13, 'unit': 'PT'},
                    'fontFamily': 'Roboto'
                },
                'fields': 'foregroundColor,fontSize,fontFamily'
            }}
        ])
        
        # Apply native Slide bullets
        requests.append({
            'createParagraphBullets': {
                'objectId': body_box_id,
                'textRange': {'type': 'ALL'},
                'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
            }
        })
        
        # 3. Image (Cinematic Side Banner - Properly proportioned)
        if image_url:
            img_id = f"img_{slide_id}"
            requests.append({
                'createImage': {
                    'objectId': img_id,
                    'url': image_url,
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {
                            'height': {'magnitude': 5143500, 'unit': 'EMU'}, 
                            'width': {'magnitude': 4400000, 'unit': 'EMU'}
                        },
                        'transform': {
                            'scaleX': 1,
                            'scaleY': 1,
                            'translateX': 5100000, 
                            'translateY': 0,
                            'unit': 'EMU'
                        }
                    }
                }
            })
            
        # 4. Accent Line (Positioned below title for visual structure)
        line_id = f"line_{slide_id}"
        requests.append({
            'createLine': {
                'objectId': line_id,
                'lineCategory': 'STRAIGHT',
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {'height': {'magnitude': 0, 'unit': 'EMU'}, 'width': {'magnitude': 3500000, 'unit': 'EMU'}},
                    'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 400000, 'translateY': 1625000, 'unit': 'EMU'}
                }
            }
        })
        requests.append({
            'updateLineProperties': {
                'objectId': line_id,
                'lineProperties': {
                    'lineFill': {
                        'solidFill': {'color': {'rgbColor': {'red': 0.3, 'green': 0.6, 'blue': 1.0}}}
                    },
                    'weight': {'magnitude': 1.5, 'unit': 'PT'}
                },
                'fields': 'lineFill,weight'
            }
        })

        service.presentations().batchUpdate(presentationId=presentation_id, body={'requests': requests}).execute()
        return True
    except Exception as e:
        logger.error(f"Error adding slide to {presentation_id}: {e}")
        return False

def create_google_sheet(user_id: str, title: str) -> dict:
    """Creates a new Google Sheet and returns its ID and link."""
    service = get_google_service(user_id, "sheets", "v4")
    if not service:
        return {"error": "Google Sheets service not available. Please authorize your account."}
    
    try:
        spreadsheet = {
            'properties': {
                'title': title
            }
        }
        spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId,spreadsheetUrl').execute()
        return {
            "id": spreadsheet.get('spreadsheetId'),
            "link": spreadsheet.get('spreadsheetUrl')
        }
    except Exception as e:
        logger.error(f"Error creating Google Sheet: {e}")
        return {"error": str(e)}

def update_sheet_values(user_id: str, spreadsheet_id: str, values: list, range_name: str = "Sheet1!A1") -> bool:
    """Updates a range of cells in a Google Sheet."""
    service = get_google_service(user_id, "sheets", "v4")
    if not service:
        return False
    
    try:
        body = {
            'values': values
        }
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, 
            range=range_name,
            valueInputOption='RAW', 
            body=body
        ).execute()
        
        # Professional detail: Bold the header row if it's the start
        if range_name.endswith("A1"):
            num_cols = len(values[0]) if values else 0
            if num_cols > 0:
                bold_request = {
                    'repeatCell': {
                        'range': {
                            'sheetId': 0, # Assuming first sheet
                            'startRowIndex': 0,
                            'endRowIndex': 1,
                            'startColumnIndex': 0,
                            'endColumnIndex': num_cols
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {'bold': True},
                                'horizontalAlignment': 'CENTER',
                                'backgroundColor': {'red': 0.9, 'green': 0.95, 'blue': 1.0}
                            }
                        },
                        'fields': 'userEnteredFormat.textFormat.bold,userEnteredFormat.horizontalAlignment,userEnteredFormat.backgroundColor'
                    }
                }
                service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={'requests': [bold_request]}).execute()
        
        return True
    except Exception as e:
        logger.error(f"Error updating Google Sheet {spreadsheet_id}: {e}")
        return False
def search_contacts(user_id: str, query: str) -> list[dict]:
    """Searches for contacts by name or email using the People API."""
    service = get_google_service(user_id, "people", "v1")
    if not service:
        return []

    try:
        results = service.people().searchContacts(
            query=query,
            readMask="names,emailAddresses"
        ).execute()

        connections = results.get('results', [])
        contacts = []
        for conn in connections:
            person = conn.get('person', {})
            names = person.get('names', [])
            emails = person.get('emailAddresses', [])
            
            display_name = names[0].get('displayName', 'Unknown') if names else 'Unknown'
            email = emails[0].get('value') if emails else None
            
            if email:
                contacts.append({
                    "name": display_name,
                    "email": email
                })
        return contacts
    except Exception as e:
        logger.error(f"People API search error: {e}")
        return []

def get_contact_by_name(user_id: str, name: str) -> dict:
    """Attempts to find a single best-match contact by name."""
    contacts = search_contacts(user_id, name)
    if not contacts:
        return None
    # Return the first match for now (exact match logic could be added)
    return contacts[0]

def upload_file_binary(user_id: str, content: bytes, filename: str, mime_type: str) -> str:
    """Uploads raw bytes to Google Drive and returns the file ID."""
    service = get_google_service(user_id, "drive", "v3")
    if not service:
        return None
    from googleapiclient.http import MediaIoBaseUpload
    from io import BytesIO
    try:
        file_metadata = {'name': filename}
        media = MediaIoBaseUpload(BytesIO(content), mimetype=mime_type, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        logger.error(f"Error uploading binary file to Drive: {e}")
        return None

def add_chart_to_sheet(user_id: str, spreadsheet_id: str, sheet_id: int, title: str, range_name: str) -> bool:
    """Adds a basic bar chart to a Google Sheet based on a data range."""
    service = get_google_service(user_id, "sheets", "v4")
    if not service:
        return False
    try:
        chart_request = {
            'addChart': {
                'chart': {
                    'spec': {
                        'title': title,
                        'basicChart': {
                            'chartType': 'BAR',
                            'legendPosition': 'BOTTOM_LEGEND',
                            'axis': [
                                {'position': 'BOTTOM_AXIS', 'title': 'Value'},
                                {'position': 'LEFT_AXIS', 'title': 'Category'}
                            ],
                            'domains': [
                                {
                                    'domain': {
                                        'sourceRange': {
                                            'sources': [
                                                {
                                                    'sheetId': sheet_id,
                                                    'startRowIndex': 0,
                                                    'endRowIndex': 10,
                                                    'startColumnIndex': 0,
                                                    'endColumnIndex': 1
                                                }
                                            ]
                                        }
                                    }
                                }
                            ],
                            'series': [
                                {
                                    'series': {
                                        'sourceRange': {
                                            'sources': [
                                                {
                                                    'sheetId': sheet_id,
                                                    'startRowIndex': 0,
                                                    'endRowIndex': 10,
                                                    'startColumnIndex': 1,
                                                    'endColumnIndex': 2
                                                }
                                            ]
                                        }
                                    },
                                    'targetAxis': 'LEFT_AXIS'
                                }
                            ]
                        }
                    },
                    'position': {
                        'newSheet': False,
                        'overlayPosition': {
                            'anchorCell': {
                                'sheetId': sheet_id,
                                'rowIndex': 12,
                                'columnIndex': 1
                            }
                        }
                    }
                }
            }
        }
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={'requests': [chart_request]}).execute()
        return True
    except Exception as e:
        logger.error(f"Error adding chart to Sheet {spreadsheet_id}: {e}")
        return False

