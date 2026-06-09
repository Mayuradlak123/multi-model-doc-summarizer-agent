from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.config import logger, settings, neo4j_manager
from app.routes import api, web

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"API configurations: Groq Active = {settings.is_groq_available}, LangSmith Active = {settings.is_langsmith_configured}")
    yield
    # Shutdown tasks
    logger.info("Shutting down application, cleaning connections...")
    try:
        neo4j_manager.close()
    except Exception as e:
        logger.error(f"Error closing Neo4j: {str(e)}")

app = FastAPI(
    title=settings.APP_NAME,
    description="Resilient Multi-Model AI Agent System summarizing documents with ChromaDB and LangSmith.",
    version="1.0.0",
    lifespan=lifespan
)

# Ensure static directories exist and mount
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Register routes
app.include_router(web.router)
app.include_router(api.router)

# Custom exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled API error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"An unexpected system error occurred: {str(exc)}"}
    )

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Running server locally at http://{settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
