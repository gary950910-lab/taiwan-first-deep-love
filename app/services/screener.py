import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
import logging
import sqlite3
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global memory cache for stock data
# Format: { ticker: { "timestamp": datetime, "data": pd.DataFrame } }
YF_CACHE = {}
CACHE_EXPIRY_MINUTES = 60

# Static Stock Database fallback
STOCK_DATABASE = {
    "tw50": [
        {"ticker": "2330.TW", "name": "台積電", "industry": "半導體業"},
        {"ticker": "2317.TW", "name": "鴻海", "industry": "電腦及週邊設備業"},
        {"ticker": "2454.TW", "name": "聯發科", "industry": "半導體業"},
        {"ticker": "2308.TW", "name": "台達電", "industry": "電子零組件業"},
        {"ticker": "2881.TW", "name": "富邦金", "industry": "金融保險業"},
        {"ticker": "2882.TW", "name": "國泰金", "industry": "金融保險業"},
        {"ticker": "2382.TW", "name": "廣達", "industry": "電腦及週邊設備業"},
        {"ticker": "2891.TW", "name": "中信金", "industry": "金融保險業"},
        {"ticker": "2303.TW", "name": "聯電", "industry": "半導體業"},
        {"ticker": "3711.TW", "name": "日月光投控", "industry": "半導體業"},
        {"ticker": "2886.TW", "name": "兆豐金", "industry": "金融保險業"},
        {"ticker": "2884.TW", "name": "玉山金", "industry": "金融保險業"},
        {"ticker": "2892.TW", "name": "第一金", "industry": "金融保險業"},
        {"ticker": "5880.TW", "name": "合庫金", "industry": "金融保險業"},
        {"ticker": "2880.TW", "name": "華南金", "industry": "金融保險業"},
        {"ticker": "2885.TW", "name": "元大金", "industry": "金融保險業"},
        {"ticker": "2883.TW", "name": "開發金", "industry": "金融保險業"},
        {"ticker": "2890.TW", "name": "永豐金", "industry": "金融保險業"},
        {"ticker": "2887.TW", "name": "台新金", "industry": "金融保險業"},
        {"ticker": "2002.TW", "name": "中鋼", "industry": "鋼鐵工業"},
        {"ticker": "1301.TW", "name": "台塑", "industry": "塑膠工業"},
        {"ticker": "1303.TW", "name": "南亞", "industry": "塑膠工業"},
        {"ticker": "1326.TW", "name": "台化", "industry": "塑膠工業"},
        {"ticker": "1101.TW", "name": "台泥", "industry": "水泥工業"},
        {"ticker": "1216.TW", "name": "統一", "industry": "食品工業"},
        {"ticker": "2912.TW", "name": "統一超", "industry": "貿易百貨業"},
        {"ticker": "3008.TW", "name": "大立光", "industry": "光電業"},
        {"ticker": "2357.TW", "name": "華碩", "industry": "電腦及週邊設備業"},
        {"ticker": "2395.TW", "name": "研華", "industry": "電腦及週邊設備業"},
        {"ticker": "3231.TW", "name": "緯創", "industry": "電腦及週邊設備業"},
        {"ticker": "4938.TW", "name": "和碩", "industry": "電腦及週邊設備業"},
        {"ticker": "2379.TW", "name": "瑞昱", "industry": "半導體業"},
        {"ticker": "3034.TW", "name": "聯詠", "industry": "半導體業"},
        {"ticker": "3443.TW", "name": "創意", "industry": "半導體業"},
        {"ticker": "3037.TW", "name": "欣興", "industry": "電子零組件業"},
        {"ticker": "2327.TW", "name": "國巨", "industry": "電子零組件業"},
        {"ticker": "2603.TW", "name": "長榮", "industry": "航運業"},
        {"ticker": "2609.TW", "name": "陽明", "industry": "航運業"},
        {"ticker": "2615.TW", "name": "萬海", "industry": "航運業"},
        {"ticker": "5871.TW", "name": "中租-KY", "industry": "其他業"},
        {"ticker": "2408.TW", "name": "南亞科", "industry": "半導體業"},
        {"ticker": "2409.TW", "name": "友達", "industry": "光電業"},
        {"ticker": "3045.TW", "name": "台灣大", "industry": "資訊服務業"},
        {"ticker": "4904.TW", "name": "遠傳", "industry": "資訊服務業"},
        {"ticker": "1402.TW", "name": "遠東新", "industry": "紡織纖維業"},
        {"ticker": "1590.TW", "name": "亞德客-KY", "industry": "電機機械業"},
        {"ticker": "2207.TW", "name": "和泰車", "industry": "汽車工業"},
        {"ticker": "2301.TW", "name": "光寶科", "industry": "電腦及週邊設備業"},
        {"ticker": "5876.TW", "name": "上海商銀", "industry": "金融保險業"},
        {"ticker": "2801.TW", "name": "彰銀", "industry": "金融保險業"}
    ],
    "listed": [
        {"ticker": "2330.TW", "name": "台積電", "industry": "半導體業"},
        {"ticker": "2317.TW", "name": "鴻海", "industry": "電腦及週邊設備業"},
        {"ticker": "2454.TW", "name": "聯發科", "industry": "半導體業"},
        {"ticker": "2382.TW", "name": "廣達", "industry": "電腦及週邊設備業"},
        {"ticker": "3231.TW", "name": "緯創", "industry": "電腦及週邊設備業"},
        {"ticker": "2337.TW", "name": "旺宏", "industry": "半導體業"},
        {"ticker": "3481.TW", "name": "群創", "industry": "光電業"},
        {"ticker": "2618.TW", "name": "長榮航", "industry": "航運業"},
        {"ticker": "2610.TW", "name": "華航", "industry": "航運業"},
        {"ticker": "2344.TW", "name": "華邦電", "industry": "半導體業"},
        {"ticker": "2324.TW", "name": "仁寶", "industry": "電腦及週邊設備業"},
        {"ticker": "2356.TW", "name": "英業達", "industry": "電腦及週邊設備業"},
        {"ticker": "2323.TW", "name": "中環", "industry": "光電業"},
        {"ticker": "2888.TW", "name": "新光金", "industry": "金融保險業"},
        {"ticker": "2883.TW", "name": "凱基金", "industry": "金融保險業"},
        {"ticker": "3702.TW", "name": "大聯大", "industry": "電子通路業"},
        {"ticker": "2353.TW", "name": "宏碁", "industry": "電腦及週邊設備業"},
        {"ticker": "2603.TW", "name": "長榮", "industry": "航運業"},
        {"ticker": "2609.TW", "name": "陽明", "industry": "航運業"},
        {"ticker": "2313.TW", "name": "華通", "industry": "電子零組件業"},
        {"ticker": "2308.TW", "name": "台達電", "industry": "電子零組件業"},
        {"ticker": "2881.TW", "name": "富邦金", "industry": "金融保險業"},
        {"ticker": "2882.TW", "name": "國泰金", "industry": "金融保險業"},
        {"ticker": "2303.TW", "name": "聯電", "industry": "半導體業"},
        {"ticker": "3711.TW", "name": "日月光投控", "industry": "半導體業"},
        {"ticker": "2886.TW", "name": "兆豐金", "industry": "金融保險業"},
        {"ticker": "2884.TW", "name": "玉山金", "industry": "金融保險業"},
        {"ticker": "2892.TW", "name": "第一金", "industry": "金融保險業"},
        {"ticker": "5880.TW", "name": "合庫金", "industry": "金融保險業"},
        {"ticker": "2880.TW", "name": "華南金", "industry": "金融保險業"},
        {"ticker": "2885.TW", "name": "元大金", "industry": "金融保險業"},
        {"ticker": "2890.TW", "name": "永豐金", "industry": "金融保險業"},
        {"ticker": "2887.TW", "name": "台新金", "industry": "金融保險業"},
        {"ticker": "2002.TW", "name": "中鋼", "industry": "鋼鐵工業"},
        {"ticker": "1301.TW", "name": "台塑", "industry": "塑膠工業"},
        {"ticker": "1303.TW", "name": "南亞", "industry": "塑膠工業"},
        {"ticker": "1101.TW", "name": "台泥", "industry": "水泥工業"},
        {"ticker": "1216.TW", "name": "統一", "industry": "食品工業"},
        {"ticker": "2912.TW", "name": "統一超", "industry": "貿易百貨業"},
        {"ticker": "3008.TW", "name": "大立光", "industry": "光電業"},
        {"ticker": "2357.TW", "name": "華碩", "industry": "電腦及週邊設備業"},
        {"ticker": "2395.TW", "name": "研華", "industry": "電腦及週邊設備業"},
        {"ticker": "4938.TW", "name": "和碩", "industry": "電腦及週邊設備業"},
        {"ticker": "2379.TW", "name": "瑞昱", "industry": "半導體業"},
        {"ticker": "3034.TW", "name": "聯詠", "industry": "半導體業"},
        {"ticker": "3443.TW", "name": "創意", "industry": "半導體業"},
        {"ticker": "3037.TW", "name": "欣興", "industry": "電子零組件業"},
        {"ticker": "2327.TW", "name": "國巨", "industry": "電子零組件業"},
        {"ticker": "2615.TW", "name": "萬海", "industry": "航運業"},
        {"ticker": "5871.TW", "name": "中租-KY", "industry": "其他業"},
        {"ticker": "2408.TW", "name": "南亞科", "industry": "半導體業"},
        {"ticker": "3045.TW", "name": "台灣大", "industry": "資訊服務業"},
        {"ticker": "4904.TW", "name": "遠傳", "industry": "資訊服務業"}
    ],
    "otc": [
        {"ticker": "5347.TWO", "name": "世界先進", "industry": "半導體業"},
        {"ticker": "6488.TWO", "name": "環球晶", "industry": "半導體業"},
        {"ticker": "8069.TWO", "name": "元太", "industry": "光電業"},
        {"ticker": "3105.TWO", "name": "穩懋", "industry": "半導體業"},
        {"ticker": "6182.TWO", "name": "合晶", "industry": "半導體業"},
        {"ticker": "5483.TWO", "name": "中美晶", "industry": "半導體業"},
        {"ticker": "3264.TWO", "name": "欣銓", "industry": "半導體業"},
        {"ticker": "8299.TWO", "name": "群聯", "industry": "半導體業"},
        {"ticker": "6147.TWO", "name": "頎邦", "industry": "半導體業"},
        {"ticker": "3529.TWO", "name": "力旺", "industry": "半導體業"},
        {"ticker": "6274.TWO", "name": "台耀", "industry": "電子零組件業"},
        {"ticker": "3293.TWO", "name": "鈊象", "industry": "文化創意業"},
        {"ticker": "5274.TWO", "name": "信驊", "industry": "半導體業"},
        {"ticker": "8086.TWO", "name": "宏捷科", "industry": "半導體業"},
        {"ticker": "5371.TWO", "name": "中光電", "industry": "光電業"},
        {"ticker": "3680.TWO", "name": "家登", "industry": "半導體業"},
        {"ticker": "8358.TWO", "name": "金居", "industry": "電子零組件業"},
        {"ticker": "4147.TWO", "name": "宣德", "industry": "電子零組件業"}
    ]
}

class YFDataService:
    @staticmethod
    def get_stock_list(market_type: str) -> List[Dict[str, str]]:
        """
        Gets list of stocks. Try to query from SQLite database first (F-05 teammate),
        if database is empty or not created yet, fall back to STOCK_DATABASE.
        """
        db_path = os.path.join("instance", "database.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                # Check if table 'stocks' exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stocks'")
                if cursor.fetchone():
                    cursor.execute("SELECT ticker, name, industry FROM stocks WHERE market_type=?", (market_type,))
                    rows = cursor.fetchall()
                    if rows:
                        logger.info(f"Loaded {len(rows)} stocks for market '{market_type}' from SQLite database.")
                        return [{"ticker": r[0], "name": r[1], "industry": r[2]} for r in rows]
                conn.close()
            except Exception as e:
                logger.error(f"Error querying SQLite database: {e}")
        
        # Fallback to static DB
        logger.info(f"Fallback: Loaded {len(STOCK_DATABASE.get(market_type, []))} stocks for market '{market_type}' from static config.")
        return STOCK_DATABASE.get(market_type, [])

    @staticmethod
    def fetch_stock_data(ticker: str) -> pd.DataFrame:
        """
        Fetches historical 1-year data for a single stock with local memory cache.
        """
        now = datetime.now()
        if ticker in YF_CACHE:
            cache_entry = YF_CACHE[ticker]
            if now - cache_entry["timestamp"] < timedelta(minutes=CACHE_EXPIRY_MINUTES):
                if not cache_entry["data"].empty:
                    return cache_entry["data"]
        
        try:
            logger.info(f"Fetching data from yfinance for {ticker}...")
            # Fetch last 1 year of daily K-lines
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty:
                logger.warning(f"No data returned for {ticker} from yfinance.")
                return pd.DataFrame()
            
            # Reset multi-index column if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Make sure index name is Date and columns are standard
            df.index.name = "Date"
            
            # Cache it
            YF_CACHE[ticker] = {
                "timestamp": now,
                "data": df
            }
            return df
        except Exception as e:
            logger.error(f"Error downloading {ticker} from yfinance: {e}")
            return pd.DataFrame()

    @classmethod
    def fetch_multiple_stocks(cls, tickers: List[str], max_workers: int = 15) -> Dict[str, pd.DataFrame]:
        """
        Downloads data for multiple stocks concurrently using a ThreadPoolExecutor.
        """
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {executor.submit(cls.fetch_stock_data, ticker): ticker for ticker in tickers}
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    df = future.result()
                    if not df.empty and len(df) >= 5:  # Need at least 5 days for indicators
                        results[ticker] = df
                except Exception as e:
                    logger.error(f"Thread execution error for {ticker}: {e}")
        return results

class ScreenerEngine:
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates MA and Volume technical indicators on the given DataFrame.
        """
        df = df.copy()
        
        # Close Price and Vol Columns
        close_col = df['Close']
        vol_col = df['Volume']
        
        # 1. Price MAs
        df['MA5'] = close_col.rolling(window=5).mean()
        df['MA10'] = close_col.rolling(window=10).mean()
        df['MA20'] = close_col.rolling(window=20).mean()
        df['MA60'] = close_col.rolling(window=60).mean()
        df['MA120'] = close_col.rolling(window=120).mean()
        df['MA240'] = close_col.rolling(window=240).mean()
        
        # 2. Volume MAs
        df['VolMA5'] = vol_col.rolling(window=5).mean()
        df['VolMA10'] = vol_col.rolling(window=10).mean()
        
        # 3. Bias Rates (乖離率) - (Close - MA) / MA * 100
        df['Bias5'] = (close_col - df['MA5']) / df['MA5'] * 100
        df['Bias10'] = (close_col - df['MA10']) / df['MA10'] * 100
        df['Bias20'] = (close_col - df['MA20']) / df['MA20'] * 100
        df['Bias60'] = (close_col - df['MA60']) / df['MA60'] * 100
        
        return df

    @classmethod
    def screen(cls, data_dict: Dict[str, pd.DataFrame], stock_info_list: List[Dict[str, str]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluates moving average and volume conditions for each stock.
        """
        matched_stocks = []
        
        # Extract filters
        ma_filters = filters.get("ma_filters", {})
        bias_filters = filters.get("bias_filters", {})
        volume_filters = filters.get("volume_filters", {})
        
        # Create ticker info mapping for fast lookups
        info_map = {item["ticker"]: item for item in stock_info_list}
        
        for ticker, df in data_dict.items():
            if df.empty or len(df) < 5:
                continue
                
            # Calculate all technical indicators
            df_ind = cls.calculate_indicators(df)
            
            # Get values of the latest day and the previous day
            latest_day = df_ind.iloc[-1]
            prev_day = df_ind.iloc[-2] if len(df_ind) > 1 else latest_day
            
            # Variables for checks
            close_price = float(latest_day['Close'])
            prev_close_price = float(prev_day['Close'])
            volume = float(latest_day['Volume'])
            
            # Calculate percentage change
            price_change_pct = 0.0
            if prev_close_price > 0:
                price_change_pct = ((close_price - prev_close_price) / prev_close_price) * 100
            
            # 1. Check MA Filters
            ma_match = True
            
            # Price above MAs
            if ma_filters.get("price_above_ma5") and not (close_price > latest_day['MA5']):
                ma_match = False
            if ma_filters.get("price_above_ma10") and not (close_price > latest_day['MA10']):
                ma_match = False
            if ma_filters.get("price_above_ma20") and not (close_price > latest_day['MA20']):
                ma_match = False
            if ma_filters.get("price_above_ma60") and not (close_price > latest_day['MA60']):
                ma_match = False
            if ma_filters.get("price_above_ma120") and not (pd.isna(latest_day['MA120']) or close_price > latest_day['MA120']):
                ma_match = False
            if ma_filters.get("price_above_ma240") and not (pd.isna(latest_day['MA240']) or close_price > latest_day['MA240']):
                ma_match = False
                
            # Short-term MA above long-term MA
            if ma_filters.get("ma5_above_ma20") and not (latest_day['MA5'] > latest_day['MA20']):
                ma_match = False
            if ma_filters.get("ma20_above_ma60") and not (latest_day['MA20'] > latest_day['MA60']):
                ma_match = False
                
            # Golden Cross (MA5 crosses above MA20)
            if ma_filters.get("golden_cross_5_20"):
                cross = (latest_day['MA5'] > latest_day['MA20']) and (prev_day['MA5'] <= prev_day['MA20'])
                if not cross:
                    ma_match = False
                    
            # Death Cross (MA5 crosses below MA20)
            if ma_filters.get("death_cross_5_20"):
                cross = (latest_day['MA5'] < latest_day['MA20']) and (prev_day['MA5'] >= prev_day['MA20'])
                if not cross:
                    ma_match = False
                    
            # MA Convergence (均線糾結 - MA5, MA10, MA20, MA60 within a certain % range)
            if ma_filters.get("ma_convergence"):
                ma_list = [latest_day['MA5'], latest_day['MA10'], latest_day['MA20'], latest_day['MA60']]
                # Drop NaNs
                ma_list = [m for m in ma_list if not pd.isna(m)]
                if len(ma_list) >= 3:
                    min_ma = min(ma_list)
                    max_ma = max(ma_list)
                    spread = ((max_ma - min_ma) / min_ma) * 100
                    threshold = float(ma_filters.get("ma_convergence_threshold", 3.0))
                    if spread > threshold:
                        ma_match = False
                else:
                    ma_match = False
                    
            if not ma_match:
                continue
                
            # 2. Check Bias Filters
            bias_match = True
            if bias_filters.get("enable"):
                period = int(bias_filters.get("ma_period", 20))
                bias_col = f"Bias{period}"
                # If bias is not calculated on the fly, calculate it
                if bias_col not in latest_day:
                    ma_val = df_ind['Close'].rolling(window=period).mean().iloc[-1]
                    bias_val = ((close_price - ma_val) / ma_val) * 100
                else:
                    bias_val = latest_day[bias_col]
                    
                if not pd.isna(bias_val):
                    min_b = float(bias_filters.get("min_bias", -2.0))
                    max_b = float(bias_filters.get("max_bias", 2.0))
                    if not (min_b <= bias_val <= max_b):
                        bias_match = False
                else:
                    bias_match = False
                    
            if not bias_match:
                continue
                
            # 3. Check Volume Filters
            volume_match = True
            min_vol_limit = float(volume_filters.get("min_volume", 0.0))
            
            # In Taiwan stock market, Volume in yfinance is in shares.
            # Volume / 1000 = "張" (Standard unit in Taiwan).
            vol_in_sheets = volume / 1000.0  
            if vol_in_sheets < min_vol_limit:
                volume_match = False
                
            vol_multiplier = float(volume_filters.get("volume_multiplier", 1.0))
            if vol_multiplier > 1.0:
                period_vol = int(volume_filters.get("volume_multiplier_period", 5))
                vol_ma_col = f"VolMA{period_vol}"
                if vol_ma_col not in latest_day:
                    avg_vol = df_ind['Volume'].rolling(window=period_vol).mean().iloc[-1]
                else:
                    avg_vol = latest_day[vol_ma_col]
                
                if avg_vol > 0:
                    if volume < (avg_vol * vol_multiplier):
                        volume_match = False
                else:
                    volume_match = False
                    
            if not volume_match:
                continue
                
            # All filters passed! Record the results
            info = info_map.get(ticker, {"name": "未知個股", "industry": "未知產業"})
            
            matched_stocks.append({
                "ticker": ticker,
                "name": info["name"],
                "industry": info["industry"],
                "close": round(close_price, 2),
                "change_pct": round(price_change_pct, 2),
                "volume": int(volume),
                "volume_sheets": round(vol_in_sheets, 1),
                "ma5": round(float(latest_day['MA5']), 2) if not pd.isna(latest_day['MA5']) else None,
                "ma20": round(float(latest_day['MA20']), 2) if not pd.isna(latest_day['MA20']) else None,
                "ma60": round(float(latest_day['MA60']), 2) if not pd.isna(latest_day['MA60']) else None,
                "bias": round(float(latest_day['Bias20']), 2) if not pd.isna(latest_day['Bias20']) else None
            })
            
        # Sort by ticker
        matched_stocks.sort(key=lambda x: x["ticker"])
        return matched_stocks
