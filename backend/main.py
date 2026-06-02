from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import json
from datetime import datetime
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor

from backend.services.database import (
    init_db, get_db_connection, get_stocks, get_unique_industries,
    save_strategy, get_strategy, get_all_strategies, delete_strategy,
    save_screener_history, get_screener_history, get_price_history, get_latest_price_date
)
from backend.services.data_sync import start_data_sync, get_sync_status
from backend.services.indicators import calculate_all_indicators
from backend.services.backtester import run_portfolio_backtest, check_strategy_conditions

app = FastAPI(title="台股多重指標選股與回測系統 API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache for stock price DataFrames to boost performance
price_df_cache = {}

@app.on_event("startup")
def startup_event():
    init_db()

# --- PYDANTIC SCHEMAS ---
class CustomConditions(BaseModel):
    macd_golden_cross: Optional[bool] = False
    macd_death_cross: Optional[bool] = False
    kd_golden_cross: Optional[bool] = False
    kd_death_cross: Optional[bool] = False
    kd_overbought: Optional[bool] = False
    kd_oversold: Optional[bool] = False
    bb_breakout: Optional[bool] = False
    bb_above_upper: Optional[bool] = False
    ma_bias_active: Optional[bool] = False
    ma_bias_op: Optional[str] = ">"  # ">" or "<"
    ma_bias_val: Optional[float] = 0.0
    ma_bias_length: Optional[int] = 60
    vol_mult_active: Optional[bool] = False
    vol_mult_val: Optional[float] = 1.5
    vol_mult_length: Optional[int] = 5
    ma_entangle_active: Optional[bool] = False
    ma_entangle_val: Optional[float] = 2.0
    high_20_day_active: Optional[bool] = False
    high_n_length: Optional[int] = 20

class StrategySchema(BaseModel):
    name: str
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    kd_k: int = 9
    kd_d: int = 3
    bb_length: int = 20
    bb_std: float = 2.0
    custom_conditions: CustomConditions

class ScreenRequest(BaseModel):
    strategy_id: Optional[int] = None
    ad_hoc_strategy: Optional[StrategySchema] = None
    date: Optional[str] = None  # Format: YYYY-MM-DD
    market: Optional[str] = None  # "上市", "上櫃"
    industry: Optional[str] = None

class BacktestRequest(BaseModel):
    strategy_id: Optional[int] = None
    ad_hoc_strategy: Optional[StrategySchema] = None
    start_date: str
    end_date: str
    initial_capital: float = 1000000.0
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    max_hold_days: int = 20
    max_positions: int = 10

class SyncRequest(BaseModel):
    start_date: Optional[str] = "2024-01-01"
    tickers: Optional[List[str]] = None

# --- BASIC ROUTES ---
@app.get("/")
def read_root():
    return {"message": "Welcome to Taiwan Stock Screener and Backtesting API"}

@app.get("/api/stocks")
def list_stocks(market: Optional[str] = None, industry: Optional[str] = None):
    return get_stocks(market=market, industry=industry)

@app.get("/api/industries")
def list_industries():
    return get_unique_industries()

# --- F-04: SINGLE STOCK PRICE HISTORY (OHLCV) API ENDPOINT ---
@app.get("/api/stocks/{ticker}/ohlcv")
def get_ohlcv(ticker: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Returns historical daily K-line prices for a specific stock ticker.
    Fulfills F-04 (OHLCV chart data).
    """
    try:
        prices = get_price_history(ticker, start_date=start_date, end_date=end_date)
        if not prices:
            raise HTTPException(status_code=404, detail=f"找不到 {ticker} 的歷史價格數據。請先至同步中心進行同步。")
        
        # Ensure JSON-safe formatting of numerical rows
        formatted_prices = []
        for p in prices:
            formatted_prices.append({
                "date": p["date"],
                "open": float(p["open"]) if not pd.isna(p["open"]) else None,
                "high": float(p["high"]) if not pd.isna(p["high"]) else None,
                "low": float(p["low"]) if not pd.isna(p["low"]) else None,
                "close": float(p["close"]) if not pd.isna(p["close"]) else None,
                "volume": int(p["volume"]) if not pd.isna(p["volume"]) else 0
            })
            
        return {
            "ticker": ticker,
            "count": len(formatted_prices),
            "prices": formatted_prices
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"讀取 K 線資料發生異常：{str(e)}")

# --- SYNC ENDPOINTS ---
@app.post("/api/sync")
def trigger_sync(req: SyncRequest):
    # Clear memory cache on sync to prevent stale stock data
    price_df_cache.clear()
    
    success, msg = start_data_sync(start_date=req.start_date, force_tickers=req.tickers)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}

@app.get("/api/sync/status")
def sync_status_endpoint():
    return get_sync_status()

# --- STRATEGIES CRUD ---
@app.get("/api/strategies")
def get_strategies():
    return get_all_strategies()

@app.post("/api/strategies")
def create_strategy(strategy: StrategySchema):
    try:
        strategy_id = save_strategy(
            name=strategy.name,
            macd_fast=strategy.macd_fast,
            macd_slow=strategy.macd_slow,
            macd_signal=strategy.macd_signal,
            kd_k=strategy.kd_k,
            kd_d=strategy.kd_d,
            bb_length=strategy.bb_length,
            bb_std=strategy.bb_std,
            custom_conditions=strategy.custom_conditions.dict()
        )
        return {"success": True, "id": strategy_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"儲存策略失敗：{str(e)}")

@app.delete("/api/strategies/{strategy_id}")
def remove_strategy(strategy_id: int):
    try:
        delete_strategy(strategy_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除策略失敗：{str(e)}")

# --- MULTI-THREADED SCREENING CORE ---
def safe_float(val):
    """Converts floats to JSON-safe float format, converting NaN or Inf to None."""
    if val is None or pd.isna(val) or np.isinf(val):
        return None
    return float(val)

def check_single_stock_screen(stock: dict, target_date: str, strategy: dict, indicator_params: dict) -> Optional[dict]:
    """Helper worker to fetch, calculate and screen a single stock."""
    ticker = stock['ticker']
    try:
        # Load from memory cache or SQLite
        if ticker in price_df_cache:
            pdf = price_df_cache[ticker]
        else:
            prices = get_price_history(ticker)
            if len(prices) < 60:
                return None
            pdf = pd.DataFrame(prices)
            pdf['date_dt'] = pd.to_datetime(pdf['date'])
            pdf.set_index('date_dt', inplace=True)
            pdf.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
            pdf = calculate_all_indicators(pdf, indicator_params)
            # Store in cache
            price_df_cache[ticker] = pdf
            
        # Locate target date
        target_dt = pd.to_datetime(target_date)
        if target_dt not in pdf.index:
            pdf_filtered = pdf[pdf.index <= target_dt]
            if pdf_filtered.empty:
                return None
            row_dt = pdf_filtered.index[-1]
            idx_pos = pdf.index.get_loc(row_dt)
        else:
            idx_pos = pdf.index.get_loc(target_dt)
            if isinstance(idx_pos, slice) or isinstance(idx_pos, np.ndarray):
                idx_pos = idx_pos[-1] if len(idx_pos) > 0 else 0
            
        # Check condition
        if check_strategy_conditions(pdf, idx_pos, strategy):
            target_row = pdf.iloc[idx_pos]
            return {
                "ticker": ticker,
                "code": stock["code"],
                "name": stock["name"],
                "market": stock["market"],
                "industry": stock["industry"],
                "close": safe_float(target_row["Close"]),
                "volume": int(target_row["Volume"]),
                "ma60_bias": safe_float(target_row.get("ma60_bias")),
                "vol_multiple": safe_float(target_row.get("vol_multiple")),
                "kd_k": safe_float(target_row.get("kd_k")),
                "kd_d": safe_float(target_row.get("kd_d")),
                "macd": safe_float(target_row.get("macd")),
                "macd_signal": safe_float(target_row.get("macd_signal")),
                "bb_lower": safe_float(target_row.get("bb_lower")),
                "bb_mid": safe_float(target_row.get("bb_mid")),
                "bb_upper": safe_float(target_row.get("bb_upper")),
                "screened_date": pdf.index[idx_pos].strftime("%Y-%m-%d")
            }
    except Exception:
        pass
    return None

# --- SCREENER ENDPOINT ---
@app.post("/api/screen")
def screen_stocks(req: ScreenRequest):
    # 1. Load Strategy
    strategy = None
    strategy_id = None
    if req.strategy_id:
        strategy = get_strategy(req.strategy_id)
        strategy_id = req.strategy_id
        if not strategy:
            raise HTTPException(status_code=404, detail="找不到指定策略")
    elif req.ad_hoc_strategy:
        strategy = req.ad_hoc_strategy.dict()
    else:
        raise HTTPException(status_code=400, detail="必須提供 strategy_id 或 ad_hoc_strategy")
        
    # 2. Determine Screening Date
    latest_date = get_latest_price_date()
    if not latest_date:
        raise HTTPException(status_code=400, detail="資料庫中尚無 K 線價格資料，請先至數據同步中心更新。")
        
    target_date = req.date if req.date else latest_date
    
    # 3. Load active stocks list
    stocks_list = get_stocks(market=req.market, industry=req.industry)
    matching_results = []
    screened_tickers = []
    
    add_conds = strategy.get('custom_conditions', {})
    
    # Parameter map for indicators
    indicator_params = {
        'macd_fast': strategy.get('macd_fast', 12),
        'macd_slow': strategy.get('macd_slow', 26),
        'macd_signal': strategy.get('macd_signal', 9),
        'kd_k_length': strategy.get('kd_k', 9),
        'kd_d_length': strategy.get('kd_d', 3),
        'bb_length': strategy.get('bb_length', 20),
        'bb_std': strategy.get('bb_std', 2.0),
        'ma_bias_length': int(add_conds.get('ma_bias_length', 60)),
        'volume_multiple_length': int(add_conds.get('volume_multiple_length', 5)),
        'entangle_threshold': float(add_conds.get('entangle_threshold', 2.0)),
        'high_n_length': int(add_conds.get('high_n_length', 20))
    }
    
    # 4. Multi-Threaded Execution using ThreadPoolExecutor
    # As required: 採用 ThreadPoolExecutor 多執行緒進行並行運算
    max_workers = min(16, os.cpu_count() * 2 if os.cpu_count() else 8)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks
        futures = [
            executor.submit(check_single_stock_screen, stock, target_date, strategy, indicator_params) 
            for stock in stocks_list
        ]
        
        # Collect results
        for f in futures:
            res = f.result()
            if res:
                matching_results.append(res)
                screened_tickers.append(res['ticker'])
                
    # Sort results by stock code
    matching_results.sort(key=lambda x: x['code'])
            
    # 5. Save screen history if a valid strategy_id is used
    if strategy_id and matching_results:
        save_screener_history(strategy_id, target_date, screened_tickers)
        
    return {
        "date": target_date,
        "strategy_name": strategy.get("name", "Ad-hoc Strategy"),
        "results_count": len(matching_results),
        "results": matching_results
    }

# --- HISTORY ROUTE ---
@app.get("/api/history")
def get_history():
    return get_screener_history()

# --- BACKTEST ENDPOINT ---
@app.post("/api/backtest")
def backtest_strategy(req: BacktestRequest):
    # 1. Load Strategy
    strategy = None
    if req.strategy_id:
        strategy = get_strategy(req.strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="找不到指定策略")
    elif req.ad_hoc_strategy:
        strategy = req.ad_hoc_strategy.dict()
    else:
        raise HTTPException(status_code=400, detail="必須提供 strategy_id 或 ad_hoc_strategy")
        
    # 2. Validate prices existence
    latest_date = get_latest_price_date()
    if not latest_date:
        raise HTTPException(status_code=400, detail="資料庫中尚無 K 線價格資料，無法執行回測。")
        
    # 3. Run backtest
    try:
        results = run_portfolio_backtest(
            strategy=strategy,
            start_date=req.start_date,
            end_date=req.end_date,
            initial_capital=req.initial_capital,
            stop_loss_pct=req.stop_loss_pct,
            take_profit_pct=req.take_profit_pct,
            max_hold_days=req.max_hold_days,
            max_positions=req.max_positions
        )
        
        # Ensure all float values returned are JSON safe
        if "summary" in results:
            for k, v in results["summary"].items():
                results["summary"][k] = safe_float(v)
                
        if "equity_curve" in results:
            for item in results["equity_curve"]:
                item["equity"] = safe_float(item["equity"])
                
        if "benchmark_curve" in results:
            for item in results["benchmark_curve"]:
                item["equity"] = safe_float(item["equity"])
                
        if "trades" in results:
            for t in results["trades"]:
                t["entry_price"] = safe_float(t["entry_price"])
                t["exit_price"] = safe_float(t["exit_price"])
                t["return_pct"] = safe_float(t["return_pct"])
                t["index_return_pct"] = safe_float(t.get("index_return_pct", 0.0))
                t["relative_return_pct"] = safe_float(t.get("relative_return_pct", 0.0))
                
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"執行策略回測失敗：{str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
