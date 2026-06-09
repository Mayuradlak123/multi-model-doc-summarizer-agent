# Multi-Model Document Summarizer Agent System

A resilient, premium web application built with **FastAPI**, **Jinja2 + Tailwind CSS**, **Redis Queue (RQ)**, **ChromaDB**, and **LangGraph**. The application processes documents up to 1MB asynchronously, extracts semantic highlights, caches results vectorially, and opens an interactive, stateful RAG Chat Agent to query the document content.

---

## ⚡ Core Features

1. **Stateful LangGraph Workflow**
   * Executes a stateful pipeline across different Groq models:
     * **Step 1: Chunk Highlight Extraction** (`llama-3.1-8b-instant`)
     * **Step 2: Global Synthesis & Deduplication** (`llama-3.3-70b-versatile`)
     * **Step 3: Executive Summary & Metadata Extraction** (`llama-3.1-8b-instant`)
2. **Stateful RAG Chat Assistant**
   * Opens an interactive chat sidebar on document completion.
   * Utilizes LangGraph's `MemorySaver` in-memory checkpointer to maintain conversation history and thread isolation within the chat session.
   * Dynamically retrieves the top 3 semantically closest chunks from ChromaDB to contextualize Groq LLM answers.
3. **Semantic Caching**
   * Employs ChromaDB vector search to cache chunk-level summaries.
   * Gated at a similarity threshold ($\le 0.15$ L2 distance squared). Bypasses LLM API calls and prints cache hit logs if a similar segment has been summarized before.
4. **Resiliency & Circuit Breakers**
   * Uses `pybreaker` to protect integrations with Groq API, ChromaDB, and Redis.
   * Gracefully falls back to synchronous in-process workers or mock data displays when databases or APIs trip circuit breakers.
5. **Real-time Observability**
   * Visual indicators on the frontend dashboard tracking circuit breaker health.
   * Live timeline showing execution stages, models used, and semantic cache hits.
   * Full LangSmith API logging tracing for debugging LLM steps.

---

## 🏗️ Project Structure

```
├── app/
│   ├── config/             # Config files, loggers, setting validation
│   │   ├── chroma_config.py
│   │   ├── circuit_breaker.py
│   │   ├── logger.py
│   │   ├── neo4j_config.py # Preserved configuration reference
│   │   ├── redis_config.py
│   │   └── settings.py
│   ├── routes/             # FastAPI Endpoint routers
│   │   ├── api.py          # API endpoints (/summarize, /chat, /health)
│   │   └── web.py          # Dashboard view router
│   ├── services/           # Service layers & LangGraph agent definitions
│   │   ├── chat_agent.py   # RAG Chat Agent state machine with MemorySaver
│   │   ├── document_parser.py
│   │   ├── state.py        # Agent state typing dicts
│   │   ├── summarizer_agent.py # Document summarizer state graph
│   │   ├── tasks.py        # RQ task worker definitions
│   │   └── vector_store.py # ChromaDB indexing & semantic cache operations
│   ├── templates/          # Jinja2 Views
│   │   ├── base.html       # Outer grid layout and imports
│   │   └── index.html      # Responsive grid, chat UI, health poller
│   ├── static/             # Static files assets
│   └── main.py             # FastAPI App initiator
├── logs/                   # Application log records
├── worker.py               # Redis Queue task daemon
├── run.sh                  # Execution shell helper
├── requirements.txt        # Dependencies
└── README.md               # Documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Redis Server installed and running:
```bash
redis-server
```

### 2. Configure Environment
Create a `.env` file in the root directory (referencing `.env.example`):
```env
GROQ_API_KEY=your_groq_key
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_TRACING_V2=true
CHROMA_API_KEY=your_chromadb_key
```
*Note: If `GROQ_API_KEY` is not present, the worker automatically operates in **Mock Mode**, simulating pipeline stages and chat agent responses for local verification.*

### 3. Installation
Install python dependencies:
```bash
pip install -r requirements.txt
```

### 4. Running the Project
Start the Redis background queue worker:
```bash
python worker.py
```

In a separate terminal, start the FastAPI web server:
```bash
./run.sh
```
Open your browser and navigate to `http://127.0.0.1:8000`.
