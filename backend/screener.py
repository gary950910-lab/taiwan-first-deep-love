import os
import pickle
import re
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
import yfinance as yf
from backend.database import get_db_connection
from backend.indicators import compute_indicators, clean_row_for_json

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".yf_cache"))
os.makedirs(CACHE_DIR, exist_ok=True)

# List of Taiwan 50 stocks (as of 2026)
TAIWAN_50_CODES = [
    "2330", "2317", "2454", "2308", "3711", "2303", "2382", "2881", "2882", "2891",
    "2886", "2885", "2884", "2892", "2890", "2880", "2883", "2887", "5880", "2889",
    "2002", "1301", "1303", "1326", "6505", "2912", "2412", "4904", "3045", "2603",
    "2609", "2615", "2357", "2383", "2395", "3008", "3037", "3231", "2301", "2327",
    "2356", "2379", "2409", "3481", "6669", "3653", "3017", "2345", "2360", "2385",
    "3661", "7769", "2059", "2207", "6919"
]

def get_cached_history(yf_symbol: str) -> pd.DataFrame:
    """
    Retrieves the cached stock historical data if it was modified today.
    """
    cache_file = os.path.join(CACHE_DIR, f"{yf_symbol}.pkl")
    if os.path.exists(cache_file):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
            # Cache is valid if downloaded today
            if mtime.date() == date.today():
                with open(cache_file, 'rb') as f:
                    df = pickle.load(f)
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        return df
        except Exception as e:
            print(f"Error reading cache for {yf_symbol}: {e}")
    return None

def save_cached_history(yf_symbol: str, df: pd.DataFrame):
    """
    Saves the stock historical data to disk cache.
    """
    cache_file = os.path.join(CACHE_DIR, f"{yf_symbol}.pkl")
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(df, f)
    except Exception as e:
        print(f"Error saving cache for {yf_symbol}: {e}")

def fetch_stock_data(yf_symbol: str) -> pd.DataFrame:
    """
    Fetches the last 1 year of historical data from yfinance, or reads from cache.
    """
    # 1. Try cache first
    df = get_cached_history(yf_symbol)
    if df is not None:
        return df
        
    # 2. Fetch from yfinance
    try:
        ticker = yf.Ticker(yf_symbol)
        # Fetch 1 year of daily K lines
        df = ticker.history(period="1y", interval="1d")
        if df.empty or len(df) < 60:
            # Try 2 years in case of suspension or lack of data
            df = ticker.history(period="2y", interval="1d")
            
        if not df.empty and len(df) >= 60:
            save_cached_history(yf_symbol, df)
            return df
    except Exception as e:
        print(f"Error downloading {yf_symbol} from yfinance: {e}")
    return None

def check_filters(latest: dict, prev: dict, filters: dict) -> bool:
    """
    Evaluates whether the technical indicators of a stock match the user criteria.
    """
    close = latest.get('close')
    if close is None or np.isnan(close):
        return False
        
    # MA60 Bias Range
    ma60_bias = latest.get('ma60_bias')
    if filters.get('ma60_bias_min') is not None:
        if ma60_bias is None or ma60_bias < float(filters['ma60_bias_min']):
            return False
    if filters.get('ma60_bias_max') is not None:
        if ma60_bias is None or ma60_bias > float(filters['ma60_bias_max']):
            return False
            
    # Bollinger Bands
    bb_upper = latest.get('bb_upper')
    bb_lower = latest.get('bb_lower')
    
    if filters.get('bb_break_upper'):
        close_prev = prev.get('close')
        bb_upper_prev = prev.get('bb_upper')
        if not (bb_upper is not None and bb_upper_prev is not None and 
                close > bb_upper and close_prev <= bb_upper_prev):
            return False
            
    if filters.get('bb_within'):
        if not (bb_lower is not None and bb_upper is not None and bb_lower <= close <= bb_upper):
            return False
            
    # KD Range
    k = latest.get('k')
    d = latest.get('d')
    if filters.get('kd_k_min') is not None:
        if k is None or k < float(filters['kd_k_min']):
            return False
    if filters.get('kd_k_max') is not None:
        if k is None or k > float(filters['kd_k_max']):
            return False
    if filters.get('kd_d_min') is not None:
        if d is None or d < float(filters['kd_d_min']):
            return False
    if filters.get('kd_d_max') is not None:
        if d is None or d > float(filters['kd_d_max']):
            return False
            
    # KD Crossovers
    if filters.get('kd_cross_up'):
        k_prev = prev.get('k')
        d_prev = prev.get('d')
        if not (k is not None and d is not None and k_prev is not None and d_prev is not None and
                k > d and k_prev <= d_prev):
            return False
    if filters.get('kd_cross_down'):
        k_prev = prev.get('k')
        d_prev = prev.get('d')
        if not (k is not None and d is not None and k_prev is not None and d_prev is not None and
                k < d and k_prev >= d_prev):
            return False
            
    # MACD Filters
    macd_dif = latest.get('macd_dif')
    macd_dem = latest.get('macd_dem')
    macd_osc = latest.get('macd_osc')
    
    if filters.get('macd_osc_positive'):
        if macd_osc is None or macd_osc <= 0:
            return False
    if filters.get('macd_osc_negative'):
        if macd_osc is None or macd_osc >= 0:
            return False
            
    # MACD Crossovers (Gold / Death Cross)
    if filters.get('macd_cross_up'):
        dif_prev = prev.get('macd_dif')
        dem_prev = prev.get('macd_dem')
        if not (macd_dif is not None and macd_dem is not None and dif_prev is not None and dem_prev is not None and
                macd_dif > macd_dem and dif_prev <= dem_prev):
            return False
    if filters.get('macd_cross_down'):
        dif_prev = prev.get('macd_dif')
        dem_prev = prev.get('macd_dem')
        if not (macd_dif is not None and macd_dem is not None and dif_prev is not None and dem_prev is not None and
                macd_dif < macd_dem and dif_prev >= dem_prev):
            return False
            
    # 20-Day High
    if filters.get('is_20d_high'):
        if not latest.get('is_20d_high'):
            return False
            
    # Volume Multiplier
    volume_ratio = latest.get('volume_ratio')
    if filters.get('volume_mult_min') is not None:
        if volume_ratio is None or volume_ratio < float(filters['volume_mult_min']):
            return False
            
    # MA Consolidation (dispersion <= threshold)
    ma_dispersion = latest.get('ma_dispersion')
    if filters.get('ma_consolidation'):
        threshold = float(filters.get('ma_consolidation_threshold', 3.0))
        if ma_dispersion is None or ma_dispersion > threshold:
            return False
            
    return True

def screen_single_stock(stock: dict, filters: dict) -> dict:
    """
    Worker function to fetch data and screen a single stock.
    """
    symbol = stock['symbol']
    name = stock['name']
    market = stock['market']
    industry = stock['industry']
    
    # Map to yfinance ticker
    yf_symbol = f"{symbol}.TW" if market == "Listed" else f"{symbol}.TWO"
    
    try:
        # Fetch history
        df = fetch_stock_data(yf_symbol)
        if df is None or len(df) < 60:
            return None
            
        # Compute indicators
        df_ind = compute_indicators(df)
        if df_ind.empty or len(df_ind) < 2:
            return None
            
        # Extract latest and previous values
        latest = df_ind.iloc[-1].to_dict()
        prev = df_ind.iloc[-2].to_dict()
        
        # Check filters
        if check_filters(latest, prev, filters):
            # Clean values for JSON compatibility
            clean_indicators = clean_row_for_json(latest)
            return {
                'symbol': symbol,
                'name': name,
                'market': market,
                'industry': industry,
                'close_price': clean_indicators.get('close'),
                'indicators': clean_indicators
            }
    except Exception as e:
        print(f"Error screening stock {symbol}: {e}")
    return None

def run_screening(scope: str, filters: dict, max_workers: int = 20) -> list:
    """
    Runs multi-threaded screening on the specified scope of stocks.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch stock list from DB based on scope
    if scope == 'Taiwan50':
        # Select stocks that belong to Taiwan 50 list
        placeholders = ','.join(['?'] * len(TAIWAN_50_CODES))
        cursor.execute(f"SELECT symbol, name, market, industry FROM stocks WHERE symbol IN ({placeholders})", TAIWAN_50_CODES)
    elif scope == 'Listed':
        cursor.execute("SELECT symbol, name, market, industry FROM stocks WHERE market = 'Listed'")
    elif scope == 'OTC':
        cursor.execute("SELECT symbol, name, market, industry FROM stocks WHERE market = 'OTC'")
    else: # 'All' or empty
        cursor.execute("SELECT symbol, name, market, industry FROM stocks")
        
    stocks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    print(f"Starting screen on {len(stocks)} stocks with {max_workers} threads...")
    matched_results = []
    
    # 2. Run multi-threaded executor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(screen_single_stock, stock, filters): stock for stock in stocks}
        for future in as_completed(futures):
            res = future.result()
            if res is not None:
                matched_results.append(res)
                
    print(f"Screening complete. Found {len(matched_results)} matching stocks.")
    return matched_results
