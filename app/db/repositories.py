from decimal import Decimal
from typing import List, Dict, Any
from app.config.postgres_config import postgres_manager
from app.config.logger import logger
from app.db.models import Document, SummaryStep, ChatMessage

def create_document(doc_id: str, filename: str, file_path: str, file_size_kb: float) -> bool:
    try:
        with postgres_manager.get_session() as session:
            if not session:
                logger.warning("PostgreSQL connection not available. Skipping create_document.")
                return False
            
            doc = Document(
                id=doc_id,
                filename=filename,
                file_path=file_path,
                file_size_kb=Decimal(str(file_size_kb))
            )
            session.merge(doc)
            return True
    except Exception as e:
        logger.error(f"Failed to create document record via SQLAlchemy: {str(e)}")
        return False

def update_document_summary(doc_id: str, summary: str) -> bool:
    try:
        with postgres_manager.get_session() as session:
            if not session:
                logger.warning("PostgreSQL connection not available. Skipping update_document_summary.")
                return False
            
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.summary = summary
                return True
            else:
                logger.warning(f"Document with ID {doc_id} not found to update summary.")
                return False
    except Exception as e:
        logger.error(f"Failed to update document summary via SQLAlchemy: {str(e)}")
        return False

def create_summary_step(doc_id: str, step_name: str, summary_text: str, processing_time_sec: float = None) -> bool:
    try:
        with postgres_manager.get_session() as session:
            if not session:
                logger.warning("PostgreSQL connection not available. Skipping create_summary_step.")
                return False
            
            # Ensure document exists to satisfy foreign key constraints
            doc_exists = session.query(Document).filter(Document.id == doc_id).first()
            if not doc_exists:
                stub_doc = Document(
                    id=doc_id,
                    filename="Unknown Document",
                    file_path=f"storage/{doc_id}_unknown",
                    file_size_kb=Decimal("0.0")
                )
                session.merge(stub_doc)
                session.flush()
            
            p_time = Decimal(str(processing_time_sec)) if processing_time_sec is not None else None
            step = SummaryStep(
                document_id=doc_id,
                step_name=step_name,
                summary_text=summary_text,
                processing_time_sec=p_time
            )
            session.add(step)
            return True
    except Exception as e:
        logger.error(f"Failed to create summary step record via SQLAlchemy: {str(e)}")
        return False

def create_chat_message(doc_id: str, thread_id: str, role: str, message: str) -> bool:
    try:
        with postgres_manager.get_session() as session:
            if not session:
                logger.warning("PostgreSQL connection not available. Skipping create_chat_message.")
                return False
            
            # Ensure document exists to satisfy foreign key constraints
            doc_exists = session.query(Document).filter(Document.id == doc_id).first()
            if not doc_exists:
                stub_doc = Document(
                    id=doc_id,
                    filename="Unknown Document",
                    file_path=f"storage/{doc_id}_unknown",
                    file_size_kb=Decimal("0.0")
                )
                session.merge(stub_doc)
                session.flush()
            
            msg = ChatMessage(
                document_id=doc_id,
                thread_id=thread_id,
                role=role,
                message=message
            )
            session.add(msg)
            return True
    except Exception as e:
        logger.error(f"Failed to create chat message record via SQLAlchemy: {str(e)}")
        return False

def get_chat_history(doc_id: str, thread_id: str) -> List[Dict[str, Any]]:
    try:
        with postgres_manager.get_session() as session:
            if not session:
                logger.warning("PostgreSQL connection not available. Skipping get_chat_history.")
                return []
            
            rows = session.query(ChatMessage)\
                          .filter(ChatMessage.document_id == doc_id, ChatMessage.thread_id == thread_id)\
                          .order_by(ChatMessage.id.asc())\
                          .all()
            
            return [
                {
                    "role": r.role,
                    "content": r.message,
                    "timestamp": r.created_at.isoformat() if r.created_at else None
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"Failed to retrieve chat history via SQLAlchemy: {str(e)}")
        return []
