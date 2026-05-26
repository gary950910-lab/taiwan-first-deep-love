from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
from api.chart import router as chart_router

app = FastAPI(
    title="智慧選股與策略回測系統 - F-04 個股 K 線與視覺化",
    description="台股 K 線繪製與技術指標視覺化系統"
)

# 設置跨域 (CORS) 讓前端可以順利對接 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 確保必要的資料夾結構存在
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# 掛載靜態資源目錄
app.mount("/static", StaticFiles(directory="static"), name="static")

# 設置 HTML 模板目錄
templates = Jinja2Templates(directory="templates")

# 註冊 K 線與技術指標 API 路由
app.include_router(chart_router)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    系統首頁路由，渲染 K 線視覺化主畫面。
    """
    return templates.TemplateResponse(request=request, name="index.html")

if __name__ == "__main__":
    import uvicorn
    # 本地開發啟動，啟用 Hot Reloading
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
