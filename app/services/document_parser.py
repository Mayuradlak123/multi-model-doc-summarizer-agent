import io
import os
from typing import List, Dict, Any
from pypdf import PdfReader
import docx
from app.config import logger

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB in bytes

def validate_file_size(file_bytes: bytes) -> bool:
    return len(file_bytes) <= MAX_FILE_SIZE

def ocr_pdf_via_vision(file_bytes: bytes) -> str:
    """
    Extracts images from PDF pages and uses Groq Vision model to perform OCR on them.
    """
    import base64
    from app.config import settings
    from groq import Groq
    
    if not settings.is_groq_available:
        logger.warning("GROQ_API_KEY is not configured. Cannot perform Vision OCR for scanned PDF.")
        return ""
        
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        
        extracted_texts = []
        client = Groq(api_key=settings.GROQ_API_KEY)
        
        for page_num, page in enumerate(reader.pages):
            logger.info(f"Extracting images from page {page_num + 1}...")
            page_text = ""
            
            for img_idx, img_obj in enumerate(page.images):
                try:
                    img_bytes = img_obj.data
                    base64_image = base64.b64encode(img_bytes).decode('utf-8')
                    
                    # Detect format (default to jpeg if name has no ext or isn't png)
                    ext = os.path.splitext(img_obj.name)[1].lower().replace(".", "")
                    if ext not in ("png", "jpeg", "jpg", "webp"):
                        ext = "jpeg"
                    if ext == "jpg":
                        ext = "jpeg"
                        
                    logger.info(f"Sending page {page_num + 1} image {img_idx + 1} to Groq Vision model...")
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Extract all readable text from this document image. Return only the extracted text. Do not add comments, intro, or description."
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/{ext};base64,{base64_image}"
                                        }
                                    }
                                ]
                            }
                        ],
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        temperature=0.1
                    )
                    ocr_text = chat_completion.choices[0].message.content.strip()
                    if ocr_text:
                        page_text += ocr_text + "\n"
                except Exception as img_err:
                    logger.error(f"Failed to perform Vision OCR on page {page_num + 1} image {img_idx + 1}: {str(img_err)}")
                    
            if page_text:
                extracted_texts.append(f"--- Page {page_num + 1} OCR Text ---\n" + page_text)
                
        return "\n\n".join(extracted_texts).strip()
    except Exception as e:
        logger.error(f"Error performing Vision OCR on PDF: {str(e)}")
        return ""

def parse_pdf(file_bytes: bytes) -> str:
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        text = ""
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        text = text.strip()
        # Fallback to Vision OCR if extracted text is empty/extremely short
        if len(text) < 100:
            logger.info("Extracted PDF text is empty or very short. Attempting Vision OCR on page images...")
            ocr_text = ocr_pdf_via_vision(file_bytes)
            if ocr_text:
                text = ocr_text
                
        return text
    except Exception as e:
        logger.error(f"Error parsing PDF: {str(e)}")
        raise ValueError(f"Failed to parse PDF document: {str(e)}")

def parse_docx(file_bytes: bytes) -> str:
    try:
        docx_file = io.BytesIO(file_bytes)
        doc = docx.Document(docx_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error parsing DOCX: {str(e)}")
        raise ValueError(f"Failed to parse DOCX document: {str(e)}")

def parse_txt(file_bytes: bytes) -> str:
    try:
        try:
            return file_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1").strip()
    except Exception as e:
        logger.error(f"Error parsing plain text: {str(e)}")
        raise ValueError(f"Failed to parse TXT document: {str(e)}")

def extract_text(file_bytes: bytes, filename: str) -> str:
    if not validate_file_size(file_bytes):
        raise ValueError(f"File size of {len(file_bytes)} bytes exceeds the maximum limit of 1 MB.")
        
    ext = os.path.splitext(filename)[1].lower()
    logger.info(f"Extracting text from file: {filename} (extension: {ext})")
    
    if ext == ".pdf":
        return parse_pdf(file_bytes)
    elif ext in (".docx", ".doc"):
        return parse_docx(file_bytes)
    elif ext in (".txt", ".md", ".markdown"):
        return parse_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Only PDF, DOCX, TXT, and Markdown/MD files are supported.")

def chunk_text(text: str, chunk_size: int = 3000, chunk_overlap: int = 500) -> List[Dict[str, Any]]:
    """
    Chunks text into structured segments with a rolling window overlap.
    """
    if not text:
        return []
        
    chunks = []
    start = 0
    text_len = len(text)
    chunk_index = 0
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            # Snap to word boundary to avoid middle-of-word cuts
            last_space = text.rfind(" ", start, end)
            if last_space != -1 and last_space > start + int(chunk_size * 0.75):
                end = last_space
                
        chunk_content = text[start:end].strip()
        if chunk_content:
            chunks.append({
                "chunk_index": chunk_index,
                "content": chunk_content,
                "length": len(chunk_content),
                "start_char": start,
                "end_char": end
            })
            chunk_index += 1
            
        start = end - chunk_overlap if end < text_len else text_len
        if start <= 0 or start >= text_len:
            break
            
    logger.info(f"Split document text into {len(chunks)} chunk(s) (Chunk Size: {chunk_size}, Overlap: {chunk_overlap})")
    return chunks
