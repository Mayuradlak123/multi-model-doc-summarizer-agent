import datetime
from sqlalchemy import Column, String, Text, Numeric, DateTime, ForeignKey, Integer
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(String(100), primary_key=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size_kb = Column(Numeric(10, 2), nullable=True)
    summary = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    steps = relationship("SummaryStep", back_populates="document", cascade="all, delete-orphan")
    chats = relationship("ChatMessage", back_populates="document", cascade="all, delete-orphan")

class SummaryStep(Base):
    __tablename__ = 'summary_steps'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(100), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    step_name = Column(String(100), nullable=False)
    summary_text = Column(Text, nullable=False)
    processing_time_sec = Column(Numeric(10, 3), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    document = relationship("Document", back_populates="steps")

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(100), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    thread_id = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    document = relationship("Document", back_populates="chats")
