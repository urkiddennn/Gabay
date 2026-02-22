import logging
import json
from gabay.core.connectors.google_api import search_drive, download_drive_file
from gabay.core.config import settings
from groq import AsyncGroq

logger = logging.getLogger(__name__)

async def handle_document_qa_skill(user_id: int, command_args_str: str) -> str:
    """
    Handles fetching a document from Google Drive and answering a question about it.
    Expects command_args_str to be JSON with 'file_query' and 'question'.
    """
    try:
        data = json.loads(command_args_str)
        file_query = data.get("file_query", "")
        question = data.get("question", "Please summarize this document.")
        
        if not file_query:
            return "Which file would you like me to look at?"
            
        # Search for the file to get ID and MIME type
        results = search_drive(str(user_id), file_query)
        if not results:
            return f"I couldn't find any file matching '{file_query}' in your Google Drive."
            
        file_info = results[0]
        file_id = file_info.get("id")
        file_name = file_info.get("title")
        mime_type = file_info.get("mimeType", "")
        
        if not file_id:
            return f"Found '{file_name}', but I couldn't retrieve its ID."
            
        # Supported MIME types for text extraction
        supported_mimes = [
            "application/vnd.google-apps.document", 
            "text/plain", 
            "text/csv", 
            "application/json",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]
        if not any(t in mime_type for t in supported_mimes):
            return f"The file '{file_name}' is a '{mime_type}', which I cannot read currently. I work best with text files, Google Docs, and Word Documents."
            
        # Download the file content
        content = download_drive_file(str(user_id), file_id, mime_type)
        if "Error downloading" in content or "Not connected" in content:
            return content
            
        # Truncate content if it's monstrously huge so we don't blow up the LLM context
        # 128k context roughly equates to ~50k words. We'll play it safe at ~15k words/100k chars.
        if len(content) > 100000:
            content = content[:100000] + "... [Document Trunkated for Length]"
            
        # Ask Groq about the document
        client = AsyncGroq(api_key=settings.groq_api_key)
        system_prompt = (
            "You are Gabay, a helpful AI assistant. You have been provided with the text of a document from the user's Google Drive. "
            "Answer the user's question based strictly on the content of the document. "
            "If the document does not contain the answer, tell the user that you cannot find the answer in the text. "
            "IMPORTANT FORMATTING RULES: You are sending this message via SMS/Telegram as PLAINTEXT. "
            "DO NOT USE ANY MARKDOWN FORMATTING AT ALL. "
            "NO asterisks (*), NO bolding (**), NO hashes (#), and NO tables. Use plain text and standard indentation or dashes (-) only."
        )
        
        user_prompt = f"Document Title: {file_name}\n\nDocument Text:\n{content}\n\n---\n\nUser Question: {question}"
        
        response = await client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        answer = response.choices[0].message.content
        return f"📄 Regarding '{file_name}':\n\n{answer}"
        
    except Exception as e:
        logger.error(f"Error in document QA skill: {e}")
        return f"I encountered an error trying to read that document: {e}"
