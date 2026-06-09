import io
import os
from typing import List, Dict, Any
from pypdf import PdfReader
import docx
from app.config import logger

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB in bytes

def validate_file_size(file_bytes: bytes) -> bool:
    return len(file_bytes) <= MAX_FILE_SIZE

def parse_pdf(file_bytes: bytes) -> str:
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        text = ""
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
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
