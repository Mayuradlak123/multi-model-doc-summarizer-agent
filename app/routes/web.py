from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()

# Templates setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    from app.config import settings
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "AI Document Highlights Extractor",
            "is_groq_configured": settings.is_groq_available,
            "is_langsmith_configured": settings.is_langsmith_configured,
            "langsmith_project": settings.LANGCHAIN_PROJECT
        }
    )
