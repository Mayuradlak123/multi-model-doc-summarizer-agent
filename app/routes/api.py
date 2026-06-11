import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from rq import Queue
from rq.job import Job
from pydantic import BaseModel

from app.config import logger, settings, redis_client, redis_breaker, llm_breaker, chroma_breaker
from app.services.tasks import process_document_task
from app.services.chat_agent import chat_agent_graph
from app.db.repositories import create_document, create_chat_message


router = APIRouter(prefix="/api")

# In-memory store for fallback jobs when Redis is offline or breaker is open
FALLBACK_JOBS = {}

@router.post("/summarize")
async def summarize_document(file: UploadFile = File(...)):
    filename = file.filename
    logger.info(f"Received document upload request for: {filename}")
    
    # Read file content
    try:
        file_bytes = await file.read()
    except Exception as e:
        logger.error(f"Error reading file stream: {str(e)}")
        raise HTTPException(status_code=400, detail="Could not read uploaded file content.")
        
    # Strict validation of file size (1MB max)
    file_size_bytes = len(file_bytes)
    if file_size_bytes > 1024 * 1024:
        logger.warning(f"File {filename} size of {file_size_bytes} bytes exceeds the 1MB limit.")
        raise HTTPException(
            status_code=400, 
            detail="File size exceeds the 1 MB limit. Please upload a smaller document."
        )
        
    # Generate unique document ID
    document_id = str(uuid.uuid4())
    
    # Store file under 'storage' directory
    try:
        os.makedirs("storage", exist_ok=True)
        file_path = os.path.join("storage", f"{document_id}_{filename}")
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        logger.info(f"Successfully saved uploaded document to disk: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save uploaded document to storage directory: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not store uploaded document on disk.")
        
    # Register document in PostgreSQL database
    db_success = create_document(
        doc_id=document_id,
        filename=filename,
        file_path=file_path,
        file_size_kb=round(file_size_bytes / 1024, 2)
    )
    if db_success:
        logger.info(f"Successfully stored document {document_id} metadata in PostgreSQL.")
    else:
        logger.warning(f"Failed to store document {document_id} metadata in PostgreSQL (DB offline or error). Proceeding.")

    # Enqueue in Redis Queue, protected by redis_breaker
    if redis_client:
        try:
            def enqueue_job():
                queue = Queue("default", connection=redis_client)
                return queue.enqueue(
                    process_document_task,
                    args=(document_id, filename, file_bytes),
                    job_timeout=600
                )
            
            # Execute with circuit breaker protection
            job = redis_breaker.call(enqueue_job)
            if job:
                job_id = job.get_id()
                logger.info(f"Successfully enqueued background task in Redis (via Circuit Breaker). Job ID: {job_id}")
                return {"job_id": job_id, "document_id": document_id, "status": "queued"}
                
        except Exception as e:
            logger.warning(f"Redis enqueuing failed or circuit breaker tripped: {str(e)}. Falling back to synchronous processing.")
            
    # Fallback to synchronous in-process execution (Redis offline / breaker open)
    job_id = f"local_{uuid.uuid4()}"
    logger.info(f"Running task synchronously under fallback job ID: {job_id}")
    
    try:
        # Execute processing synchronously in the main thread
        result = process_document_task(document_id, filename, file_bytes)
        FALLBACK_JOBS[job_id] = {
            "status": "finished",
            "progress_step": "completed",
            "result": result
        }
    except ValueError as ve:
        logger.warning(f"Validation failure during synchronous processing: {str(ve)}")
        FALLBACK_JOBS[job_id] = {
            "status": "failed",
            "error": str(ve)
        }
    except Exception as e:
        logger.error(f"Fallback synchronous processing failed: {str(e)}", exc_info=True)
        FALLBACK_JOBS[job_id] = {
            "status": "failed",
            "error": str(e)
        }
        
    return {"job_id": job_id, "document_id": document_id, "status": "finished" if "result" in FALLBACK_JOBS[job_id] else "failed"}


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    # Check fallback job store first
    if job_id.startswith("local_"):
        if job_id in FALLBACK_JOBS:
            return FALLBACK_JOBS[job_id]
        raise HTTPException(status_code=404, detail="Fallback job execution session not found.")
        
    # Check Redis Queue job
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis client is offline. Local jobs not found.")
        
    try:
        # Protect job fetching via redis_breaker
        def fetch_job():
            return Job.fetch(job_id, connection=redis_client)
            
        job = redis_breaker.call(fetch_job)
    except Exception as e:
        logger.warning(f"Job {job_id} not found or Redis breaker open: {str(e)}")
        raise HTTPException(status_code=404, detail="Requested background task job not found or Redis connection refused.")
        
    status = job.get_status()
    progress_step = job.meta.get('progress_step', '')
    
    result = None
    error = None
    
    if status == 'finished':
        result = job.result
    elif status == 'failed':
        error = job.exc_info or "Background task crashed in Redis worker."
        if error and len(error) > 400:
            error = error[:400] + "..."
            
    return {
        "job_id": job_id,
        "status": status,
        "progress_step": progress_step,
        "result": result,
        "error": error
    }

@router.get("/system/health")
async def get_system_health():
    """Returns the current state of all circuit breakers."""
    return {
        "services": {
            "groq_llm": {
                "state": llm_breaker.state.name,
                "tripped": llm_breaker.state.name == "open"
            },
            "chromadb": {
                "state": chroma_breaker.state.name,
                "tripped": chroma_breaker.state.name == "open"
            },
            "redis_cache": {
                "state": redis_breaker.state.name,
                "tripped": redis_breaker.state.name == "open"
            }
        }
    }

class ChatRequest(BaseModel):
    document_id: str
    message: str
    session_id: str = None

@router.post("/chat")
async def chat_with_document(req: ChatRequest):
    """Invokes the stateful chat agent LangGraph to answer user questions about a document."""
    thread_id = req.session_id if req.session_id else req.document_id
    config = {"configurable": {"thread_id": thread_id}}
    
    inputs = {
        "document_id": req.document_id,
        "question": req.message
    }
    
    logger.info(f"Invoking stateful RAG Chat Agent for thread_id: {thread_id}, document_id: {req.document_id}")
    
    try:
        result = chat_agent_graph.invoke(inputs, config)
        
        # Save user query and assistant response in PostgreSQL
        answer = result.get("answer", "")
        create_chat_message(
            doc_id=req.document_id,
            thread_id=thread_id,
            role="user",
            message=req.message
        )
        create_chat_message(
            doc_id=req.document_id,
            thread_id=thread_id,
            role="assistant",
            message=answer
        )
        
        return {
            "answer": answer,
            "chat_history": result.get("chat_history", [])
        }
    except Exception as e:
        logger.error(f"Failed to execute chat agent step: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while communicating with the document assistant: {str(e)}"
        )

