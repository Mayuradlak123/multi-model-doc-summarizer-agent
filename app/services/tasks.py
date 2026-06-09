import uuid
from typing import Dict, Any
from app.services.document_parser import extract_text, chunk_text
from app.services.vector_store import vector_store_service
from app.services.summarizer_agent import run_summarization_pipeline, update_job_progress
from app.config import logger

def process_document_task(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    logger.info(f"Redis Task Worker initiated processing for document: {filename} ({len(file_bytes)} bytes)")
    
    # 1. Text Parsing & Validation
    try:
        update_job_progress("ingested")
        text = extract_text(file_bytes, filename)
    except Exception as e:
        logger.error(f"Failed to parse uploaded document inside worker: {str(e)}")
        raise ValueError(f"Document parsing error: {str(e)}")
        
    if not text.strip():
        raise ValueError("Document contains empty or unreadable text content.")
        
    # 2. Slice Content into Chunks
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("Document chunk segmentation failed.")
        
    # 3. Vector Database Indexing
    document_id = str(uuid.uuid4())
    indexed_successfully = vector_store_service.index_document(document_id, chunks, filename)
    
    # 4. Trigger LangGraph State Machine
    try:
        pipeline_result = run_summarization_pipeline(filename, chunks)
    except Exception as e:
        logger.error(f"LangGraph execution crashed: {str(e)}")
        raise ValueError(f"Agent state workflow failure: {str(e)}")
        
    # 5. Enrich result statistics
    pipeline_result["document_id"] = document_id
    pipeline_result["file_size_kb"] = round(len(file_bytes) / 1024, 2)
    pipeline_result["num_chunks"] = len(chunks)
    pipeline_result["indexed_successfully"] = indexed_successfully
    
    logger.info(f"Redis Task Worker completed document processing for: {filename}")
    return pipeline_result
