import os
import logging
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import pytesseract
from PIL import Image
from gabay.core.connectors.google_api import get_google_service, download_drive_file, search_drive
from gabay.core.config import settings

logger = logging.getLogger(__name__)

async def handle_pdf_skill(user_id: str, args_json: str) -> str:
    import json
    try:
        data = json.loads(args_json)
        action = data.get("action")
        
        if action == "merge":
            return await merge_pdfs(user_id, data.get("file_queries", []), data.get("output_name", "Merged_Document.pdf"))
        elif action == "sign":
            return await sign_pdf(user_id, data.get("file_query"), data.get("signature_text", "Digitally Signed"), data.get("output_name"))
        elif action == "ocr":
            return await ocr_pdf(user_id, data.get("file_query"))
        else:
            return "Unknown PDF action. Supported: merge, sign, ocr."
    except Exception as e:
        logger.error(f"PDF skill error: {e}")
        return f"Error processing PDF request: {e}"

async def merge_pdfs(user_id: str, queries: list[str], output_name: str) -> str:
    if not queries or len(queries) < 2:
        return "Please provide at least two PDF names to merge."
    
    writer = PdfWriter()
    found_files = []
    
    for q in queries:
        files = search_drive(user_id, q)
        pdf_files = [f for f in files if "pdf" in f.get("mimeType", "").lower()]
        if pdf_files:
            found_files.append(pdf_files[0])
        else:
            return f"Could not find PDF matching '{q}'."

    for f in found_files:
        content = download_drive_file_binary(user_id, f["id"])
        if isinstance(content, str):
            return f"Error downloading {f['title']}: {content}"
        
        reader = PdfReader(BytesIO(content))
        for page in reader.pages:
            writer.add_page(page)
            
    output_stream = BytesIO()
    writer.write(output_stream)
    
    from gabay.core.connectors.google_api import upload_file_binary
    file_id = upload_file_binary(user_id, output_stream.getvalue(), output_name, "application/pdf")
    return f"Successfully merged {len(found_files)} PDFs into '{output_name}'! [View here](https://drive.google.com/file/d/{file_id}/view)"

async def sign_pdf(user_id: str, query: str, text: str, output_name: str = None) -> str:
    files = search_drive(user_id, query)
    pdf_files = [f for f in files if "pdf" in f.get("mimeType", "").lower()]
    if not pdf_files:
        return f"Could not find PDF matching '{query}'."
    
    f = pdf_files[0]
    if not output_name:
        output_name = f"Signed_{f['title']}"
        
    content = download_drive_file_binary(user_id, f["id"])
    if isinstance(content, str):
        return f"Error downloading: {content}"
        
    can.setFillColorRGB(0.1, 0.1, 0.5) 
    # Stamp signature at bottom right
    can.drawString(450, 50, text)
    can.save()
    packet.seek(0)
    
    new_pdf = PdfReader(packet)
    existing_pdf = PdfReader(BytesIO(content))
    writer = PdfWriter()
    
    # Stamp first page
    page = existing_pdf.pages[0]
    page.merge_page(new_pdf.pages[0])
    
    for p in existing_pdf.pages:
        writer.add_page(p)
        
    output_stream = BytesIO()
    writer.write(output_stream)
    
    from gabay.core.connectors.google_api import upload_file_binary
    file_id = upload_file_binary(user_id, output_stream.getvalue(), output_name, "application/pdf")
    return f"Document '{f['title']}' has been signed as '{output_name}'! [View here](https://drive.google.com/file/d/{file_id}/view)"

async def ocr_pdf(user_id: str, query: str) -> str:
    files = search_drive(user_id, query)
    # OCR works best on images; PDF requires conversion
    target = next((f for f in files if any(it in f['mimeType'] for it in ['image', 'pdf'])), None)
    
    if not target:
        return f"Could not find an image or PDF matching '{query}'."
        
    content = download_drive_file_binary(user_id, target["id"])
    if isinstance(content, str):
        return f"Error downloading: {content}"
        
    # Assume image; PDF OCR requires pdf2image
    try:
        img = Image.open(BytesIO(content))
        text = pytesseract.image_to_string(img)
        
        from gabay.core.connectors.google_api import create_google_doc
        doc_result = create_google_doc(user_id, f"OCR Result: {target['title']}", text)
        return f"OCR Complete! Extracted text from '{target['title']}' and saved to Google Docs: [View Result]({doc_result['link']})"
    except Exception as e:
        return f"OCR Error: {e}. (PDF OCR requires pdf2image, not yet installed.)"

def download_drive_file_binary(user_id: str, file_id: str) -> bytes:
    """Download raw bytes from Drive."""
    service = get_google_service(user_id, "drive", "v3")
    if not service: return "Service missing"
    try:
        request = service.files().get_media(fileId=file_id)
        return request.execute()
    except Exception as e:
        return str(e)
