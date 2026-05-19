from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import time
import logging
from app.services.screener import YFDataService, ScreenerEngine

logger = logging.getLogger(__name__)

router = APIRouter()

class MAFiltersInput(BaseModel):
    price_above_ma5: bool = False
    price_above_ma10: bool = False
    price_above_ma20: bool = False
    price_above_ma60: bool = False
    price_above_ma120: bool = False
    price_above_ma240: bool = False
    ma5_above_ma20: bool = False
    ma20_above_ma60: bool = False
    golden_cross_5_20: bool = False
    death_cross_5_20: bool = False
    ma_convergence: bool = False
    ma_convergence_threshold: float = 3.0

class BiasFiltersInput(BaseModel):
    enable: bool = False
    ma_period: int = 20
    min_bias: float = -2.0
    max_bias: float = 2.0

class VolumeFiltersInput(BaseModel):
    min_volume: float = 0.0  # in sheets (張)
    volume_multiplier: float = 1.0  # e.g., 2.0 means > 2x of N-day average
    volume_multiplier_period: int = 5

class ScreenRequestInput(BaseModel):
    market_type: str = "tw50"  # tw50, listed, otc
    ma_filters: MAFiltersInput = Field(default_factory=MAFiltersInput)
    bias_filters: BiasFiltersInput = Field(default_factory=BiasFiltersInput)
    volume_filters: VolumeFiltersInput = Field(default_factory=VolumeFiltersInput)

@router.post("/screen")
def run_screening(payload: ScreenRequestInput):
    """
    Executes core stock screening calculations based on the provided filters.
    """
    logger.info(f"Received screening request for market: {payload.market_type}")
    start_time = time.time()
    
    # 1. Get stock list
    stock_list = YFDataService.get_stock_list(payload.market_type)
    if not stock_list:
        raise HTTPException(status_code=400, detail=f"No stock configurations found for market '{payload.market_type}'.")
        
    tickers = [item["ticker"] for item in stock_list]
    
    # 2. Concurrently fetch yfinance data
    logger.info(f"Downloading historical data for {len(tickers)} stocks...")
    data_dict = YFDataService.fetch_multiple_stocks(tickers)
    
    # 3. Apply filters via ScreenerEngine
    logger.info("Applying core filtering logic...")
    matched_results = ScreenerEngine.screen(data_dict, stock_list, payload.model_dump())
    
    elapsed_time = time.time() - start_time
    logger.info(f"Screening complete. Scanned: {len(tickers)}, Matched: {len(matched_results)}, Time: {elapsed_time:.2f}s")
    
    return {
        "status": "success",
        "market_type": payload.market_type,
        "scanned_count": len(tickers),
        "matched_count": len(matched_results),
        "execution_time_seconds": round(elapsed_time, 2),
        "results": matched_results
    }
