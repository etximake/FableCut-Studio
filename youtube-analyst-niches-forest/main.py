import logging
import socket
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.core.config import settings
from src.api.routes import router as api_router

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Hệ thống AI tự động phân tích video ngắn qua Contact Sheet 3x3 và biên kịch lời bình CapCut theo Skill."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount thư mục static
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(api_router)

@app.get("/")
async def serve_ui():
    """Giao diện chính Commentary Studio"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs"
    }

@app.get("/api/info")
async def api_info():
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "endpoints": {
            "process_video": "/api/v1/commentary/process-video",
            "rewrite_commentary": "/api/v1/commentary/rewrite",
            "list_skills": "/api/v1/skills",
            "sfx_catalog": "/api/v1/sfx/catalog",
            "ai_status": "/api/v1/ai/status"
        }
    }

def get_free_port(preferred_port: int, host: str = "0.0.0.0") -> int:
    """Tự động tìm cổng còn trống nếu cổng mặc định (ví dụ 8000) bị chiếm dụng"""
    for p in range(preferred_port, preferred_port + 50):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, p))
                return p
        except OSError:
            continue
    return preferred_port

if __name__ == "__main__":
    import socket
    host = settings.get_var("HOST", "0.0.0.0")
    requested_port = int(settings.get_var("PORT", "8000"))
    actual_port = get_free_port(requested_port, host)
    
    if actual_port != requested_port:
        logger.warning(
            f"Port {requested_port} dang bi chiem boi ung dung khac! "
            f"Tu dong chuyen sang port: {actual_port}"
        )

    display_host = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host
    logger.info(f"Starting {settings.APP_NAME} on http://{display_host}:{actual_port}")
    logger.info(f"Swagger API Docs: http://{display_host}:{actual_port}/docs")

    # Mặc định reload=False để chạy đơn tiến trình gắn chặt vào terminal của bạn.
    # Khi bạn bấm [X] hoặc Ctrl+C để tắt terminal run.bat, server sẽ tắt sạch lập tức 100%.
    dev_reload = settings.get_var("DEV_RELOAD", "false").lower() == "true"
    if dev_reload:
        uvicorn.run("main:app", host=host, port=actual_port, reload=True)
    else:
        uvicorn.run(app, host=host, port=actual_port)
