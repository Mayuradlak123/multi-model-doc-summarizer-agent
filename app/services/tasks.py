import time
import os
import uuid
from typing import Dict, Any
from app.services.document_parser import extract_text, chunk_text
from app.services.vector_store import vector_store_service
from app.services.summarizer_agent import run_summarization_pipeline, update_job_progress
from app.config import logger
from app.db.repositories import create_document, update_document_summary, create_summary_step

def process_document_task(document_id: str, filename: str, file_bytes: bytes) -> Dict[str, Any]:
    logger.info(f"Redis Task Worker initiated processing for document ID: {document_id}, filename: {filename}")
    
    # Ensure document exists in DB (especially for fallback/local execution paths)
    file_path = os.path.join("storage", f"{document_id}_{filename}")
    file_size_kb = round(len(file_bytes) / 1024, 2)
    create_document(document_id, filename, file_path, file_size_kb)
    
    # 1. Text Parsing & Validation
    t0 = time.perf_counter()
    try:
        update_job_progress("ingested")
        text = extract_text(file_bytes, filename)
        duration = time.perf_counter() - t0
        create_summary_step(
            document_id, 
            "file_ingested", 
            f"Document text parsed successfully ({len(text)} characters)", 
            duration
        )
    except Exception as e:
        duration = time.perf_counter() - t0
        create_summary_step(
            document_id, 
            "file_ingested_failed", 
            f"Failed to parse document: {str(e)}", 
            duration
        )
        logger.error(f"Failed to parse uploaded document inside worker: {str(e)}")
        raise ValueError(f"Document parsing error: {str(e)}")
        
    if not text.strip():
        create_summary_step(
            document_id, 
            "validation_failed", 
            "Document contains empty or unreadable text content", 
            0.0
        )
        raise ValueError("Document contains empty or unreadable text content.")
        
    # 2. Slice Content into Chunks
    t1 = time.perf_counter()
    chunks = chunk_text(text)
    if not chunks:
        create_summary_step(
            document_id, 
            "chunking_failed", 
            "Document chunk segmentation failed", 
            time.perf_counter() - t1
        )
        raise ValueError("Document chunk segmentation failed.")
        
    # 3. Vector Database Indexing
    indexed_successfully = vector_store_service.index_document(document_id, chunks, filename)
    duration_indexing = time.perf_counter() - t1
    create_summary_step(
        document_id,
        "vector_indexing",
        f"Segmented text into {len(chunks)} chunks and indexed in vector store (success={indexed_successfully})",
        duration_indexing
    )
    
    # 4. Trigger LangGraph State Machine
    t2 = time.perf_counter()
    try:
        pipeline_result = run_summarization_pipeline(document_id, filename, chunks)
        duration_pipeline = time.perf_counter() - t2
        create_summary_step(
            document_id,
            "summarization_pipeline",
            f"LangGraph summarization workflow completed with {len(pipeline_result.get('highlights', []))} highlights",
            duration_pipeline
        )
        # Save executive summary in DB
        update_document_summary(document_id, pipeline_result.get("executive_summary", ""))
    except Exception as e:
        duration_pipeline = time.perf_counter() - t2
        create_summary_step(
            document_id,
            "summarization_pipeline_failed",
            f"LangGraph execution crashed: {str(e)}",
            duration_pipeline
        )
        logger.error(f"LangGraph execution crashed: {str(e)}")
        raise ValueError(f"Agent state workflow failure: {str(e)}")
        
    # 5. Enrich result statistics
    pipeline_result["document_id"] = document_id
    pipeline_result["file_size_kb"] = file_size_kb
    pipeline_result["num_chunks"] = len(chunks)
    pipeline_result["indexed_successfully"] = indexed_successfully
    
    logger.info(f"Redis Task Worker completed document processing for: {filename}")
    return pipeline_result

