from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes_api import router as api_router
from app.config.settings import settings
from app.database.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database & application services...")
    init_db()
    logger.info("Autonomous Job Application Agent server is ready!")
    yield


# Initialize FastAPI application
app = FastAPI(
    title="Autonomous Job Application Agent",
    description="Multi-tech role AI job discovery, match scoring, and Excel application tracker",
    version="1.0.0",
    lifespan=lifespan
)

# Template configuration
templates_dir = settings.resolve_path("app/templates")
templates_dir.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Include API routes
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serve the single-page interactive web GUI dashboard."""
    return templates.TemplateResponse(request=request, name="index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
