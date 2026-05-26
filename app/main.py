from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routes.screen import router as screen_router
import os

app = FastAPI(
    title="Smart Stock Screener",
    description="智慧選股與策略回測系統 - 核心選股引擎模組",
    version="1.0.0"
)

# Allow CORS for easier development/testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(screen_router, prefix="/api")

# Ensure static directories exist
os.makedirs(os.path.join("app", "static"), exist_ok=True)
os.makedirs(os.path.join("app", "static", "css"), exist_ok=True)
os.makedirs(os.path.join("app", "static", "js"), exist_ok=True)

# Mount the static directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def get_index():
    """
    Serves the main dashboard application.
    """
    index_path = os.path.join("app", "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": "Smart Stock Screener API is running.",
        "hint": "Please create index.html in app/static to render the beautiful dashboard UI!"
    }
