import json
import os
import uuid
from typing import List, Dict, Any, Tuple
from groq import Groq
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from langgraph.graph import StateGraph, START, END
from rq import get_current_job

from app.config import settings, logger, llm_breaker, with_breaker
from .state import AgentState
from app.services.vector_store import vector_store_service

# Initialize groq client if key is set
groq_client = None
if settings.is_groq_available:
    try:
        groq_client = Groq(api_key=settings.GROQ_API_KEY)
        logger.info("Groq API client successfully initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {str(e)}")
else:
    logger.warning("GROQ_API_KEY is not configured. Running summarizer in Mock Mode.")

# Models configuration
MODEL_STEP_1 = "llama-3.1-8b-instant"
MODEL_STEP_2 = "llama-3.3-70b-versatile"
MODEL_STEP_3 = "llama-3.1-8b-instant"

# Mock summary data for testing without API keys
MOCK_SUMMARY_DATA = {
    "executive_summary": "This document outlines the architectural specifications and design principles of the new enterprise microservice platform. It details how the integration of ChromaDB for semantic vector searches and Redis for caching facilitates low-latency performance. The system utilizes circuit breakers to maintain high availability under peak loads.",
    "tone": "Professional & Technical",
    "category": "Software Architecture Specification",
    "entities": ["ChromaDB", "Redis", "Neo4j", "FastAPI", "Groq API", "LangSmith"],
    "highlights": [
        {
            "topic": "System Integration & Database Layout",
            "bullets": [
                "ChromaDB handles vector storage for semantic retrieval and high-dimensional document search.",
                "Neo4j provides relational graph database capabilities for tracking multi-agent interaction logs.",
                "Redis acts as the transient caching layer for rapidly serving session states."
            ]
        },
        {
            "topic": "Resilience & Circuit Breakers",
            "bullets": [
                "Pybreaker is integrated across external LLM and database clients to prevent cascading failures.",
                "Breakers automatically trip after 3 sequential failures and require a recovery timeout.",
                "Fallback functions return structural mock data or cached items during downtime."
            ]
        },
        {
            "topic": "FastAPI Web Stack & Agent Configuration",
            "bullets": [
                "FastAPI routes handle file uploads up to 1MB, feeding content into a chunking pipeline.",
                "Jinja2 and Tailwind CSS provide a responsive dashboard showcasing multi-model execution stages.",
                "LangSmith integration traces the entire call stack of the AI agent for observability."
            ]
        }
    ]
}

def generate_mock_result(filename: str) -> Dict[str, Any]:
    mock_copy = MOCK_SUMMARY_DATA.copy()
    mock_copy["filename"] = filename
    mock_copy["document_id"] = str(uuid.uuid4())
    mock_copy["is_mock"] = True
    mock_copy["trace_url"] = "https://smith.langchain.com/o/mock-org/projects/p/mock-project?run_id=mock-run"
    mock_copy["steps_timeline"] = [
        {"step": "Step 1: Chunk Highlight Extraction", "model": f"{MODEL_STEP_1} (MOCK)", "status": "Completed successfully"},
        {"step": "Step 2: Global Synthesis & Deduplication", "model": f"{MODEL_STEP_2} (MOCK)", "status": "Completed successfully"},
        {"step": "Step 3: Executive Summary & Meta-Analysis", "model": f"{MODEL_STEP_3} (MOCK)", "status": "Completed successfully"}
    ]
    return mock_copy

# Helper function to report progress back to the Redis queue worker
def update_job_progress(progress_step: str):
    try:
        job = get_current_job()
        if job:
            job.meta['progress_step'] = progress_step
            job.save_meta()
            logger.info(f"Updated Redis Job {job.get_id()} progress step to: {progress_step}")
    except Exception as e:
        logger.warning(f"Failed to update Redis job progress state: {str(e)}")

def call_groq_llm(model: str, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    """Wrapper to make Groq API calls inside the circuit breaker."""
    if not groq_client:
        raise ValueError("Groq client not initialized")
        
    response_format = {"type": "json_object"} if json_mode else None
    
    completion = groq_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
        response_format=response_format
    )
    return completion.choices[0].message.content

@traceable(name="Step 1: Extract Chunk Highlights")
def extract_chunk_highlights(chunk_content: str, chunk_index: int) -> str:
    logger.info(f"Running Step 1 (Chunk {chunk_index}) using {MODEL_STEP_1}")
    system_prompt = "You are an expert information extractor. Extract the core highlights, facts, and key points from this text chunk as bullet points. Be concise. Start bullet points with '-'."
    user_prompt = f"Text Chunk {chunk_index}:\n\n{chunk_content}"
    
    # Run inside circuit breaker
    call_fn = lambda: call_groq_llm(MODEL_STEP_1, system_prompt, user_prompt)
    response = llm_breaker.call(call_fn)
    
    # Save to semantic cache on success
    if response:
        try:
            vector_store_service.update_cache(chunk_content, response)
        except Exception as e:
            logger.warning(f"Failed to update semantic cache: {str(e)}")
            
    return response

@traceable(name="Step 2: Synthesize Global Highlights")
def synthesize_global_highlights(raw_highlights: List[str]) -> str:
    logger.info(f"Running Step 2 (Global Synthesis) using {MODEL_STEP_2}")
    system_prompt = (
        "You are an expert editor. Synthesize the following bullet points collected from different sections of a document into a structured summary. "
        "Deduplicate information. Group the bullet points logically under 2 to 4 clear thematic headings/topics. "
        "Format the output using Markdown like this:\n\n"
        "### Topic Name\n"
        "- Bullet point 1\n"
        "- Bullet point 2\n\n"
        "### Another Topic Name\n"
        "- Bullet point 3"
    )
    
    aggregated_bullets = "\n".join([f"Section {i+1} highlights:\n{h}" for i, h in enumerate(raw_highlights)])
    user_prompt = f"Aggregated bullet points:\n\n{aggregated_bullets}"
    
    call_fn = lambda: call_groq_llm(MODEL_STEP_2, system_prompt, user_prompt)
    response = llm_breaker.call(call_fn)
    return response

@traceable(name="Step 3: Meta-Analysis & Executive Summary")
def run_meta_analysis(synthesized_markdown: str) -> Dict[str, Any]:
    logger.info(f"Running Step 3 (Meta-Analysis) using {MODEL_STEP_3}")
    system_prompt = (
        "You are an advanced meta-analyst. Analyze the following document summary and output a JSON object containing:\n"
        "1. 'executive_summary': A list of 3 concise sentences summarizing the main points.\n"
        "2. 'tone': The overall tone of the document (e.g. professional, alarming, casual, technical).\n"
        "3. 'category': The general category of the document (e.g. architecture specification, research paper, marketing brochure).\n"
        "4. 'entities': A list of up to 8 key products, technologies, organizations, or people mentioned.\n\n"
        "Your output must be a valid JSON object only. Do not wrap in markdown blocks, just return the raw JSON string."
    )
    
    user_prompt = f"Document Summary:\n\n{synthesized_markdown}"
    
    call_fn = lambda: call_groq_llm(MODEL_STEP_3, system_prompt, user_prompt, json_mode=True)
    response_str = llm_breaker.call(call_fn)
    
    try:
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Failed to parse JSON response from step 3: {str(e)}. Raw response: {response_str}")
        return {
            "executive_summary": ["Failed to parse structured meta-analysis. Document synthesis completed successfully."],
            "tone": "Informational",
            "category": "General Document",
            "entities": []
        }

def parse_markdown_highlights(md_text: str) -> List[Dict[str, Any]]:
    """Helper to convert Markdown summaries with topics into structured dictionaries for the frontend."""
    sections = []
    current_section = None
    
    for line in md_text.split("\n"):
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("###") or line.startswith("##") or line.startswith("#"):
            topic = line.replace("#", "").strip()
            current_section = {"topic": topic, "bullets": []}
            sections.append(current_section)
        elif line.startswith("-") or line.startswith("*"):
            bullet = line[1:].strip()
            if current_section is not None:
                current_section["bullets"].append(bullet)
            else:
                current_section = {"topic": "Key Highlights", "bullets": [bullet]}
                sections.append(current_section)
                
    if not sections:
        # Fallback if markdown didn't have headings
        sections = [{"topic": "Key Highlights", "bullets": [line.strip("- *") for line in md_text.split("\n") if line.strip()]}]
        
    return sections

# ----------------- LangGraph State Machine Definition -----------------
from .state import AgentState

def extract_chunks_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node to extract facts from individual chunks."""
    update_job_progress("indexed")
    
    chunks = state["chunks"]
    filename = state["filename"]
    is_mock = state["is_mock"]
    
    timeline = list(state.get("steps_timeline", []))
    
    if is_mock:
        return {
            "raw_highlights": ["Mock bullet 1", "Mock bullet 2"],
            "steps_timeline": timeline + [
                {"step": "Step 1: Chunk Highlight Extraction", "model": f"{MODEL_STEP_1} (MOCK)", "status": "Simulated"}
            ]
        }
        
    raw_highlights = []
    cache_hits = 0
    for c in chunks:
        # Check semantic cache first
        cached_highlights = vector_store_service.check_cache(c["content"])
        if cached_highlights:
            logger.info(f"⚡ Re-using cached highlights for chunk {c['chunk_index']} of {filename}")
            raw_highlights.append(cached_highlights)
            cache_hits += 1
        else:
            highlight = extract_chunk_highlights(c["content"], c["chunk_index"])
            raw_highlights.append(highlight)
            
    status_msg = f"Processed {len(chunks)} chunks"
    if cache_hits > 0:
        status_msg += f" ({cache_hits} semantic cache hits)"
        
    return {
        "raw_highlights": raw_highlights,
        "steps_timeline": timeline + [
            {"step": "Step 1: Chunk Highlight Extraction", "model": MODEL_STEP_1, "status": status_msg}
        ]
    }

def synthesize_highlights_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node to merge and synthesis the extracted facts."""
    update_job_progress("step_1_done")
    
    raw_highlights = state["raw_highlights"]
    is_mock = state["is_mock"]
    
    timeline = list(state.get("steps_timeline", []))
    
    if is_mock:
        return {
            "synthesized_markdown": "### Highlights\n- Mock bullet point",
            "steps_timeline": timeline + [
                {"step": "Step 2: Global Synthesis & Deduplication", "model": f"{MODEL_STEP_2} (MOCK)", "status": "Simulated"}
            ]
        }
        
    synthesized_md = synthesize_global_highlights(raw_highlights)
    return {
        "synthesized_markdown": synthesized_md,
        "steps_timeline": timeline + [
            {"step": "Step 2: Global Synthesis & Deduplication", "model": MODEL_STEP_2, "status": "Topics grouped"}
        ]
    }

def meta_analysis_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node to run document meta-analysis (tone, category, summary, entities)."""
    update_job_progress("step_2_done")
    
    synthesized_md = state["synthesized_markdown"]
    is_mock = state["is_mock"]
    
    timeline = list(state.get("steps_timeline", []))
    
    if is_mock:
        mock_res = MOCK_SUMMARY_DATA
        return {
            "executive_summary": mock_res["executive_summary"],
            "tone": mock_res["tone"],
            "category": mock_res["category"],
            "entities": mock_res["entities"],
            "steps_timeline": timeline + [
                {"step": "Step 3: Executive Summary & Meta-Analysis", "model": f"{MODEL_STEP_3} (MOCK)", "status": "Simulated"}
            ]
        }
        
    meta_result = run_meta_analysis(synthesized_md)
    return {
        "executive_summary": meta_result.get("executive_summary", ""),
        "tone": meta_result.get("tone", ""),
        "category": meta_result.get("category", ""),
        "entities": meta_result.get("entities", []),
        "steps_timeline": timeline + [
            {"step": "Step 3: Executive Summary & Meta-Analysis", "model": MODEL_STEP_3, "status": "Completed"}
        ]
    }

# Build and compile the state graph
builder = StateGraph(AgentState)
builder.add_node("extract_chunks", extract_chunks_node)
builder.add_node("synthesize_highlights", synthesize_highlights_node)
builder.add_node("meta_analysis", meta_analysis_node)

builder.add_edge(START, "extract_chunks")
builder.add_edge("extract_chunks", "synthesize_highlights")
builder.add_edge("synthesize_highlights", "meta_analysis")
builder.add_edge("meta_analysis", END)

summarizer_graph = builder.compile()

# ---------------------------------------------------------

@traceable(name="Document Summarization Pipeline")
def run_summarization_pipeline(filename: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Runs the stateful summarizer graph workflow."""
    is_mock = not settings.is_groq_available
    
    # Trace observers log ID
    run_tree = get_current_run_tree()
    run_id = run_tree.id if run_tree else uuid.uuid4()
    
    # Initialize state
    initial_state = {
        "filename": filename,
        "chunks": chunks,
        "raw_highlights": [],
        "synthesized_markdown": "",
        "executive_summary": "",
        "tone": "",
        "category": "",
        "entities": [],
        "is_mock": is_mock,
        "steps_timeline": [],
        "error": ""
    }
    
    try:
        logger.info("Triggering LangGraph state workflow...")
        final_state = summarizer_graph.invoke(initial_state)
        
        # Render highlights
        highlights = parse_markdown_highlights(final_state["synthesized_markdown"])
        if is_mock:
            highlights = MOCK_SUMMARY_DATA["highlights"]
            
        trace_url = f"{settings.LANGCHAIN_ENDPOINT}/o/default/projects/p/{settings.LANGCHAIN_PROJECT}/r/{run_id}"
        if not settings.is_langsmith_configured:
            trace_url = None
            
        return {
            "document_id": str(uuid.uuid4()),
            "filename": filename,
            "executive_summary": final_state["executive_summary"],
            "tone": final_state["tone"],
            "category": final_state["category"],
            "entities": final_state["entities"],
            "highlights": highlights,
            "is_mock": is_mock,
            "trace_url": trace_url if not is_mock else "https://smith.langchain.com/o/mock-org/projects/p/mock-project?run_id=mock-run",
            "steps_timeline": final_state["steps_timeline"]
        }
    except Exception as e:
        logger.error(f"Failed to execute state graph pipeline: {str(e)}")
        raise e
