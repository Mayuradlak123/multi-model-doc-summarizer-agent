import os
import sys
import uuid
from typing import List, Dict, Any

# Ensure project root is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("Doc-Summarizer-Agent")

@mcp.tool()
def list_documents() -> List[Dict[str, Any]]:
    """List all documents processed in the system, including their ID, filename, file size, and final summary."""
    from app.config.postgres_config import postgres_manager
    from app.db.models import Document
    
    try:
        with postgres_manager.get_session() as session:
            if not session:
                return [{"error": "Database connection not available"}]
            docs = session.query(Document).order_by(Document.uploaded_at.desc()).all()
            return [
                {
                    "document_id": d.id,
                    "filename": d.filename,
                    "file_path": d.file_path,
                    "file_size_kb": float(d.file_size_kb) if d.file_size_kb is not None else 0.0,
                    "summary": d.summary or "No summary generated yet.",
                    "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None
                }
                for d in docs
            ]
    except Exception as e:
        return [{"error": f"Failed to query database: {str(e)}"}]

@mcp.tool()
def summarize_local_file(file_path: str) -> Dict[str, Any]:
    """Reads a local PDF, DOCX, or TXT file, saves a copy to storage, and executes the multi-model summarization and chunking pipeline. Returns stats and summary."""
    from app.services.tasks import process_document_task
    
    if not os.path.exists(file_path):
        return {"error": f"File path not found: {file_path}"}
        
    try:
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            
        document_id = str(uuid.uuid4())
        
        # Execute the processing task synchronously
        result = process_document_task(document_id, filename, file_bytes)
        return {
            "success": True,
            "document_id": document_id,
            "filename": filename,
            "executive_summary": result.get("executive_summary", ""),
            "tone": result.get("tone", ""),
            "category": result.get("category", ""),
            "entities": result.get("entities", []),
            "num_chunks": result.get("num_chunks", 0),
            "timeline": result.get("steps_timeline", [])
        }
    except Exception as e:
        return {"error": f"Failed to run summarization pipeline: {str(e)}"}

@mcp.tool()
def chat_with_document(document_id: str, question: str, session_id: str = None) -> Dict[str, Any]:
    """Ask a question about a processed document using the RAG chat agent. Preserves session memory if session_id is provided."""
    from app.services.chat_agent import chat_agent_graph
    from app.db.repositories import create_chat_message
    
    thread_id = session_id if session_id else document_id
    config = {"configurable": {"thread_id": thread_id}}
    
    inputs = {
        "document_id": document_id,
        "question": question
    }
    
    try:
        result = chat_agent_graph.invoke(inputs, config)
        answer = result.get("answer", "")
        
        # Record chat history in database
        create_chat_message(
            doc_id=document_id,
            thread_id=thread_id,
            role="user",
            message=question
        )
        create_chat_message(
            doc_id=document_id,
            thread_id=thread_id,
            role="assistant",
            message=answer
        )
        
        return {
            "answer": answer,
            "chat_history_length": len(result.get("chat_history", []))
        }
    except Exception as e:
        return {"error": f"Failed to answer question: {str(e)}"}

@mcp.tool()
def get_pipeline_timeline(document_id: str) -> List[Dict[str, Any]]:
    """Retrieve the step-by-step progress and timing logs of the summarization pipeline for a processed document."""
    from app.config.postgres_config import postgres_manager
    from app.db.models import SummaryStep
    
    try:
        with postgres_manager.get_session() as session:
            if not session:
                return [{"error": "Database connection not available"}]
            steps = session.query(SummaryStep).filter(SummaryStep.document_id == document_id).order_by(SummaryStep.id.asc()).all()
            return [
                {
                    "step_name": s.step_name,
                    "summary_text": s.summary_text,
                    "processing_time_sec": float(s.processing_time_sec) if s.processing_time_sec is not None else None,
                    "created_at": s.created_at.isoformat() if s.created_at else None
                }
                for s in steps
            ]
    except Exception as e:
        return [{"error": f"Failed to retrieve step logs: {str(e)}"}]

if __name__ == "__main__":
    # Standard FastMCP CLI execution
    mcp.run()
