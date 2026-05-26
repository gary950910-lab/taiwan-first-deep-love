import json
from datetime import datetime, date
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import get_db_connection, init_db
from backend.scraper import scrape_stocks
from backend.screener import run_screening, fetch_stock_data
from backend.indicators import compute_indicators, clean_row_for_json
from backend.backtester import run_backtest_simulation

# Initialize DB on startup
init_db()

app = FastAPI(title="Taiwan Stock Screener & Backtester API")

# Configure CORS
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

# Request Models
class FiltersModel(BaseModel):
    ma60_bias_min: Optional[float] = None
    ma60_bias_max: Optional[float] = None
    bb_break_upper: Optional[bool] = False
    bb_within: Optional[bool] = False
    kd_k_min: Optional[float] = None
    kd_k_max: Optional[float] = None
    kd_d_min: Optional[float] = None
    kd_d_max: Optional[float] = None
    kd_cross_up: Optional[bool] = False
    kd_cross_down: Optional[bool] = False
    macd_osc_positive: Optional[bool] = False
    macd_osc_negative: Optional[bool] = False
    macd_cross_up: Optional[bool] = False
    macd_cross_down: Optional[bool] = False
    is_20d_high: Optional[bool] = False
    volume_mult_min: Optional[float] = None
    ma_consolidation: Optional[bool] = False
    ma_consolidation_threshold: Optional[float] = 3.0

class ScreenRequest(BaseModel):
    scope: str  # 'Taiwan50', 'Listed', 'OTC', 'All'
    filters: FiltersModel
    save_session: Optional[bool] = True

class BacktestRequest(BaseModel):
    session_id: int
    stop_loss_pct: float
    take_profit_pct: float
    max_holding_days: Optional[int] = 60

# API Endpoints
@app.get("/api/stocks")
def get_stocks(query: Optional[str] = None):
    """
    Returns list of all stocks, optionally filtered by name or symbol.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if query:
            cursor.execute("""
                SELECT symbol, name, market, industry 
                FROM stocks 
                WHERE symbol LIKE ? OR name LIKE ?
                LIMIT 100
            """, (f"%{query}%", f"%{query}%"))
        else:
            cursor.execute("SELECT symbol, name, market, industry FROM stocks LIMIT 100")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/sync")
def sync_stock_list(background_tasks: BackgroundTasks):
    """
    Triggers the scraper to update stock definitions in background.
    """
    background_tasks.add_task(scrape_stocks)
    return {"status": "success", "message": "TWSE/TPEx stock synchronization started in the background."}

@app.post("/api/screen")
def screen_stocks(req: ScreenRequest):
    """
    Screens stocks based on filters, optionally saves session to SQLite.
    """
    try:
        filters_dict = req.filters.dict()
        # Clean None values to avoid passing them unnecessarily
        cleaned_filters = {k: v for k, v in filters_dict.items() if v is not None}
        
        results = run_screening(req.scope, cleaned_filters)
        
        session_id = None
        timestamp = datetime.now().isoformat()
        
        if req.save_session:
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # 1. Create a session record
                cursor.execute("""
                    INSERT INTO screening_sessions (timestamp, scope, filters_json, matched_count)
                    VALUES (?, ?, ?, ?)
                """, (timestamp, req.scope, json.dumps(cleaned_filters), len(results)))
                session_id = cursor.lastrowid
                
                # 2. Bulk insert matching results
                for r in results:
                    cursor.execute("""
                        INSERT INTO screening_results (session_id, symbol, name, close_price, industry, indicators_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        session_id,
                        r['symbol'],
                        r['name'],
                        r['close_price'],
                        r['industry'],
                        json.dumps(r['indicators'])
                    ))
                conn.commit()
            except Exception as db_err:
                conn.rollback()
                print(f"Error saving session: {db_err}")
                raise HTTPException(status_code=500, detail=f"Database save error: {db_err}")
            finally:
                conn.close()
                
        return {
            "session_id": session_id,
            "timestamp": timestamp,
            "scope": req.scope,
            "matched_count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
def get_sessions():
    """
    Returns list of all saved screening sessions.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, timestamp, scope, filters_json, matched_count FROM screening_sessions ORDER BY id DESC")
        rows = cursor.fetchall()
        sessions = []
        for r in rows:
            d = dict(r)
            d['filters'] = json.loads(d['filters_json'])
            sessions.append(d)
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/sessions/{session_id}")
def get_session_details(session_id: int):
    """
    Returns details of a specific screening session, including matched stocks.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, timestamp, scope, filters_json, matched_count FROM screening_sessions WHERE id = ?", (session_id,))
        s_row = cursor.fetchone()
        if not s_row:
            raise HTTPException(status_code=404, detail="Session not found")
            
        session = dict(s_row)
        session['filters'] = json.loads(session['filters_json'])
        
        cursor.execute("SELECT symbol, name, close_price, industry, indicators_json FROM screening_results WHERE session_id = ?", (session_id,))
        r_rows = cursor.fetchall()
        
        results = []
        for r in r_rows:
            stock_res = dict(r)
            stock_res['indicators'] = json.loads(stock_res['indicators_json'])
            results.append(stock_res)
            
        session['results'] = results
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: int):
    """
    Deletes a screening session and all its matching results.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM screening_sessions WHERE id = ?", (session_id,))
        # SQLite foreign key cascade should delete from screening_results if configured,
        # but let's delete manually to be safe.
        cursor.execute("DELETE FROM screening_results WHERE session_id = ?", (session_id,))
        conn.commit()
        return {"status": "success", "message": f"Session {session_id} deleted."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/backtest")
def run_backtest(req: BacktestRequest):
    """
    Runs the backtest simulation for a saved session.
    """
    try:
        res = run_backtest_simulation(
            session_id=req.session_id,
            stop_loss_pct=req.stop_loss_pct,
            take_profit_pct=req.take_profit_pct,
            max_holding_days=req.max_holding_days
        )
        return res
    except ValueError as val_err:
        raise HTTPException(status_code=404, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kline/{symbol}")
def get_kline(symbol: str, period: str = "1y"):
    """
    Fetches historical OHLCV data with technical indicators computed on it for Charting.
    """
    # 1. Resolve stock market details
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, market, industry FROM stocks WHERE symbol = ?", (symbol,))
    row = cursor.fetchone()
    conn.close()
    
    # Defaults in case the user requests a stock we don't have cataloged yet
    if not row:
        # Default fallback
        name = "Unknown Stock"
        market = "OTC" if symbol.startswith(('3', '5', '6', '8')) and len(symbol) == 4 else "Listed"
        industry = "Unknown"
    else:
        name = row['name']
        market = row['market']
        industry = row['industry']
        
    yf_symbol = f"{symbol}.TW" if market == "Listed" else f"{symbol}.TWO"
    
    # 2. Fetch history
    df = fetch_stock_data(yf_symbol)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Failed to load historical data for {yf_symbol}")
        
    # 3. Compute indicators
    try:
        df_ind = compute_indicators(df)
    except Exception as ind_err:
        raise HTTPException(status_code=500, detail=f"Indicator error: {ind_err}")
        
    # 4. Format historical bars
    klines = []
    for t_date, r in df_ind.iterrows():
        # Lightweight charts demands time format 'YYYY-MM-DD'
        date_str = t_date.strftime("%Y-%m-%d") if isinstance(t_date, (date, datetime)) else str(t_date)
        
        raw_indicators = {
            'ma5': r.get('ma5'),
            'ma10': r.get('ma10'),
            'ma20': r.get('ma20'),
            'ma60': r.get('ma60'),
            'bb_upper': r.get('bb_upper'),
            'bb_mid': r.get('bb_mid'),
            'bb_lower': r.get('bb_lower'),
            'k': r.get('k'),
            'd': r.get('d'),
            'macd_dif': r.get('macd_dif'),
            'macd_dem': r.get('macd_dem'),
            'macd_osc': r.get('macd_osc'),
        }
        
        klines.append({
            'time': date_str,
            'open': float(r['open']) if not pd.isna(r['open']) else 0.0,
            'high': float(r['high']) if not pd.isna(r['high']) else 0.0,
            'low': float(r['low']) if not pd.isna(r['low']) else 0.0,
            'close': float(r['close']) if not pd.isna(r['close']) else 0.0,
            'volume': float(r['volume']) if not pd.isna(r['volume']) else 0.0,
            'indicators': clean_row_for_json(raw_indicators)
        })
        
    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "industry": industry,
        "klines": klines
    }

# Serve Frontend static assets
# Ensure the folder frontend exists
import os
os.makedirs("frontend", exist_ok=True)

# Mount frontend as static files under /static
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def read_root():
    """
    Serves the main frontend entrypoint HTML.
    """
    index_path = os.path.join("frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Taiwan Stock Screener Backend is running. Frontend index.html not found yet."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
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
