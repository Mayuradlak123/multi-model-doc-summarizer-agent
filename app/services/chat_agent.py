import os
from typing import List, Dict, Any, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings, logger, llm_breaker
from app.services.vector_store import vector_store_service

# Define chat agent state
class ChatAgentState(TypedDict):
    document_id: str
    question: str
    context: str
    chat_history: List[Dict[str, str]]  # Holds role and content pairs
    answer: str

def answer_question_node(state: ChatAgentState) -> Dict[str, Any]:
    """LangGraph node that performs RAG querying and generates context-aware stateful answers."""
    document_id = state["document_id"]
    question = state["question"]
    chat_history = list(state.get("chat_history", []))
    
    # 1. Retrieve top 3 relevant chunks from ChromaDB
    context_text = ""
    context_chunks = []
    try:
        context_chunks = vector_store_service.query_document(document_id, question, n_results=3)
        context_text = "\n\n".join([c["content"] for c in context_chunks])
        logger.info(f"Retrieved {len(context_chunks)} context chunks from ChromaDB for document: {document_id}")
    except Exception as e:
        logger.error(f"Failed to query ChromaDB for RAG context: {str(e)}")
        
    # 2. Build system prompt including retrieved context
    system_prompt = (
        "You are an expert AI document assistant. Answer the user's questions strictly based on the provided retrieved context. "
        "Maintain a helpful, concise, and professional tone. If the answer cannot be found in the context, say that the context does "
        "not contain that information (do not make up answers).\n\n"
        f"Retrieved Context:\n{context_text}"
    )
    
    # 3. Assemble chat messages matching standard structure
    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})
    
    # 4. Generate answer using Groq under LLM Circuit Breaker (or mock fallback)
    is_mock = not settings.is_groq_available
    if is_mock:
        # Construct mock response summarizing retrieved chunk ids/titles
        chunk_snippets = [f"[Chunk {c['metadata'].get('chunk_index', 'N/A')}]: {c['content'][:60]}..." for c in context_chunks]
        chunk_summary = " ".join(chunk_snippets) if chunk_snippets else "No matching document segments retrieved."
        answer = (
            f"[MOCK CHAT RESPONSE] You asked: '{question}'. Since Groq is not configured, here is a mock response "
            f"simulated from the retrieved document segments: {chunk_summary}"
        )
    else:
        try:
            # Import groq client dynamically to prevent import side effects
            from app.services.summarizer_agent import groq_client
            if not groq_client:
                raise ValueError("Groq client not initialized")
                
            def call_groq():
                completion = groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=messages,
                    temperature=0.3
                )
                return completion.choices[0].message.content
                
            answer = llm_breaker.call(call_groq)
        except Exception as e:
            logger.error(f"Error in RAG LLM call or breaker tripped: {str(e)}")
            answer = "The AI document assistant is currently offline. Please try again in a few seconds."
            
    # 5. Append new interaction to the history
    updated_history = chat_history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer}
    ]
    
    return {
        "chat_history": updated_history,
        "answer": answer,
        "context": context_text
    }

# Build and compile state graph with MemorySaver checkpointer
builder = StateGraph(ChatAgentState)
builder.add_node("answer_question", answer_question_node)
builder.add_edge(START, "answer_question")
builder.add_edge("answer_question", END)

memory = MemorySaver()
chat_agent_graph = builder.compile(checkpointer=memory)
