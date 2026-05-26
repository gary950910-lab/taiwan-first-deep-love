from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn

import database

app = FastAPI(title="Taiwan Stock Screener API")

# 設定 CORS 以允許前端存取
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 應用程式啟動時初始化資料庫
@app.on_event("startup")
def startup_event():
    database.init_db()

# Models
class ScanResultModel(BaseModel):
    ticker: str
    price: Optional[float] = None
    volume: Optional[int] = None
    indicators: Optional[Dict[str, Any]] = {}

class ScanRecordRequest(BaseModel):
    scan_date: str
    strategy_name: str
    conditions: Dict[str, Any]
    results: List[ScanResultModel]

@app.get("/api/records", summary="取得歷史掃描紀錄列表")
def get_records():
    try:
        records = database.get_all_records()
        return {"status": "success", "data": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/records/{history_id}", summary="取得單筆紀錄明細")
def get_record_detail(history_id: int):
    try:
        record = database.get_record_detail(history_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"status": "success", "data": record}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/records", summary="儲存一筆新的掃描紀錄")
def save_record(request: ScanRecordRequest):
    try:
        results_dicts = [r.dict() for r in request.results]
        history_id = database.save_scan_record(
            scan_date=request.scan_date,
            strategy_name=request.strategy_name,
            conditions=request.conditions,
            results=results_dicts
        )
        return {"status": "success", "history_id": history_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/records/{history_id}", summary="刪除特定掃描紀錄")
def delete_record(history_id: int):
    try:
        deleted = database.delete_record(history_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"status": "success", "message": f"Record {history_id} deleted."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
