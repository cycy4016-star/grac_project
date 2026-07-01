"""
UI routes — serves the GRaC web interface.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

UI_DIR = Path(__file__).parent / "static"

router = APIRouter(tags=["ui"])


@router.get("/", include_in_schema=False)
async def index():
    return FileResponse(UI_DIR / "index.html")


@router.get("/app", include_in_schema=False)
async def app_spa():
    return FileResponse(UI_DIR / "index.html")


@router.get("/chat/{path:path}", include_in_schema=False)
async def chat_spa(path: str):
    return FileResponse(UI_DIR / "index.html")


@router.get("/admin", include_in_schema=False)
async def admin_index():
    return FileResponse(UI_DIR / "admin" / "index.html")


@router.get("/admin/{path:path}", include_in_schema=False)
async def admin_spa(path: str):
    return FileResponse(UI_DIR / "admin" / "index.html")


def mount_static(app):
    if (UI_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(UI_DIR / "css")), name="css")
    if (UI_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(UI_DIR / "js")), name="js")
    if (UI_DIR / "admin" / "css").exists():
        app.mount("/admin/css", StaticFiles(directory=str(UI_DIR / "admin" / "css")), name="admin_css")
    if (UI_DIR / "admin" / "js").exists():
        app.mount("/admin/js", StaticFiles(directory=str(UI_DIR / "admin" / "js")), name="admin_js")
