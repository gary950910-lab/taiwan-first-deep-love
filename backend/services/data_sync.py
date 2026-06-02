import requests
import re
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime
import threading
from backend.services.database import get_db_connection, insert_stocks, insert_stock_prices

# Global variable to track sync status
sync_status = {
    "is_running": False,
    "progress": 0,
    "current_task": "Idle",
    "message": "",
    "processed_count": 0,
    "total_count": 0,
    "logs": []
}

def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {msg}"
    sync_status["logs"].append(log_line)
    # Limit logs to last 100 lines
    if len(sync_status["logs"]) > 100:
        sync_status["logs"].pop(0)
    print(log_line)

def get_sync_status():
    return sync_status

# A list of top active Taiwan stock tickers as default pool (~350 stocks)
# It covers Taiwan 50, Mid-cap 100, and major liquid stocks in each sector
DEFAULT_CORE_TICKERS = [
    # ETF / Index
    "^TWII", "0050.TW", "0056.TW", "00878.TW", "00919.TW", "00929.TW",
    # Semiconductors (半導體)
    "2330.TW", "2454.TW", "2303.TW", "3711.TW", "2337.TW", "2344.TW", "3034.TW", "2408.TW", "3532.TW", "3264.TWO", "5347.TWO", "6488.TWO", "3081.TWO", "3105.TWO", "8086.TWO", "3227.TWO", "4966.TWO",
    # Computers & Peripherals (電腦及週邊)
    "2317.TW", "2382.TW", "2357.TW", "2308.TW", "3231.TW", "2324.TW", "2356.TW", "2353.TW", "2377.TW", "2376.TW", "2301.TW", "2395.TW", "3017.TW", "6669.TW", "3515.TW", "6125.TWO", "8069.TWO",
    # Electronic Parts & components (電子零組件)
    "2327.TW", "3037.TW", "3189.TW", "3044.TW", "2492.TW", "2383.TW", "6271.TW", "6213.TW", "3008.TW", "3406.TW", "5483.TWO", "6182.TWO", "6261.TWO",
    # Communications (通信網路)
    "2412.TW", "4904.TW", "3045.TW", "2345.TW", "5388.TW", "3234.TWO", "4906.TW", "6426.TWO",
    # Shipping (航運)
    "2603.TW", "2609.TW", "2615.TW", "2618.TW", "2610.TW", "2605.TW", "2606.TW", "2637.TW", "5608.TWO",
    # Financials (金融)
    "2881.TW", "2882.TW", "2886.TW", "2891.TW", "2884.TW", "2885.TW", "2892.TW", "2880.TW", "2883.TW", "2887.TW", "2890.TW", "5880.TW", "2851.TW", "6005.TW", "2834.TW", "5876.TW",
    # Steel & Heavy Industry (鋼鐵、電機)
    "2002.TW", "2014.TW", "2027.TW", "2009.TW", "1504.TW", "1513.TW", "1519.TW", "1503.TW", "1605.TW", "2371.TW",
    # Optoelectronics (光電)
    "2409.TW", "3481.TW", "6116.TW", "2448.TW", "3050.TW",
    # Others / Traditional Industries
    "1101.TW", "1102.TW", "1301.TW", "1303.TW", "1326.TW", "1402.TW", "1216.TW", "2105.TW", "2633.TW", "2912.TW", "9904.TW", "9910.TW", "9921.TW", "9945.TW",
    # High-interest/volatile OTC (上櫃熱門)
    "8046.TW", "3293.TWO", "5425.TWO", "6147.TWO", "8299.TWO", "6510.TWO", "6180.TWO", "3529.TWO", "4105.TWO", "4128.TWO", "4162.TWO"
]

def clean_taiwan_stock_html(url, market):
    """
    Scrapes TWSE/TPEx ISIN listings page and extracts stock codes, names, and industry sectors.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    add_log(f"正在爬取 {market} 股票基本資料自: {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.SSLError:
        add_log(f"警告：{market} 網路請求遇到 SSL 憑證驗證問題，正在嘗試忽略 SSL 憑證驗證進行抓取...")
        response = requests.get(url, headers=headers, timeout=15, verify=False)
    except Exception as e:
        add_log(f"錯誤：無法連線至 {url}，原因：{str(e)}")
        return []
        
    response.encoding = "big5" # TWSE ISIN table uses Big5 encoding
    
    if response.status_code != 200:
        add_log(f"錯誤：無法連線至 {url}，HTTP 狀態碼 {response.status_code}")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.find_all("tr")
    
    extracted_stocks = []
    
    # Standard format:
    # Column 0: 有價證券代號及名稱 (e.g. "2330　台台積電" or "2330  台積電")
    # Column 3: 上市日 / 上櫃日
    # Column 4: 市場屬性 ("上市" or "上櫃")
    # Column 5: 產業別 (e.g. "半導體業")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
            
        col0_text = cells[0].get_text().strip()
        market_type = cells[4].get_text().strip()
        industry_type = cells[5].get_text().strip()
        
        # We only want standard stocks (either 上市 or 上櫃)
        if market_type != market:
            continue
            
        # Parse ticker code and name from col0
        # Typical format is Code + IDEOGRAPHIC SPACE (\u3000) or SPACES + Name
        match = re.match(r"^(\d{4,6})\s+(.+)$", col0_text)
        if not match:
            # Try splitting by unicode space
            match = re.match(r"^(\d{4,6})\u3000+(.+)$", col0_text)
            
        if match:
            code = match.group(1)
            name = match.group(2).strip()
            
            # yfinance ticker suffix
            suffix = ".TW" if market == "上市" else ".TWO"
            ticker = f"{code}{suffix}"
            
            extracted_stocks.append({
                "ticker": ticker,
                "code": code,
                "name": name,
                "market": market,
                "industry": industry_type
            })
            
    add_log(f"成功解析 {market} 股票共 {len(extracted_stocks)} 檔")
    return extracted_stocks

def sync_stock_list():
    """
    Crawls both TWSE and TPEx websites, parses active stocks, and updates the local SQLite database.
    """
    twse_url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    tpex_url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"
    
    listed_stocks = clean_taiwan_stock_html(twse_url, "上市")
    otc_stocks = clean_taiwan_stock_html(tpex_url, "上櫃")
    
    all_stocks = listed_stocks + otc_stocks
    
    if all_stocks:
        add_log(f"正在寫入資料庫 stocks 表，共計 {len(all_stocks)} 檔個股...")
        insert_stocks(all_stocks)
        add_log("股票基本清單同步完成！")
    else:
        add_log("警告：未能爬取到任何股票清單，可能結構變更或網路問題。")
        
    return len(all_stocks)

def sync_prices_worker(start_date=None, force_tickers=None):
    """
    Background worker thread that runs the historical prices downloader.
    """
    global sync_status
    sync_status["is_running"] = True
    sync_status["progress"] = 0
    sync_status["logs"] = []
    
    try:
        add_log("=== 開始執行市場資料同步作業 ===")
        
        # 1. Sync Stock Tickers List
        sync_status["current_task"] = "Syncing Stock Catalog"
        sync_status["message"] = "正在從證交所與櫃買中心獲取最新股票清單..."
        ticker_count = sync_stock_list()
        
        # 2. Get list of tickers to download
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if force_tickers:
            # Use user-specified tickers (clean and construct correct list)
            tickers_to_sync = []
            for t in force_tickers:
                t = t.strip().upper()
                if not t.endswith(".TW") and not t.endswith(".TWO") and t != "^TWII":
                    # Check in DB
                    cursor.execute("SELECT ticker FROM stocks WHERE code = ?", (t,))
                    row = cursor.fetchone()
                    if row:
                        tickers_to_sync.append(row['ticker'])
                    else:
                        # Guess listed
                        tickers_to_sync.append(f"{t}.TW")
                else:
                    tickers_to_sync.append(t)
        else:
            # We download the DEFAULT_CORE_TICKERS.
            # Plus any ticker already in the DB that has is_active = 1 and was manually added
            cursor.execute("SELECT ticker FROM stocks WHERE is_active = 1")
            db_tickers = [row['ticker'] for row in cursor.fetchall()]
            
            # Combine core list and database active tickers
            combined = set(DEFAULT_CORE_TICKERS + db_tickers)
            
            # Make sure all combined are in the database (or are the index ^TWII)
            tickers_to_sync = []
            for t in combined:
                if t == "^TWII":
                    tickers_to_sync.append(t)
                else:
                    cursor.execute("SELECT ticker FROM stocks WHERE ticker = ?", (t,))
                    if cursor.fetchone():
                        tickers_to_sync.append(t)
        
        conn.close()
        
        # Ensure we have the benchmark index
        if "^TWII" not in tickers_to_sync:
            tickers_to_sync.append("^TWII")
            
        total_tickers = len(tickers_to_sync)
        sync_status["total_count"] = total_tickers
        sync_status["processed_count"] = 0
        sync_status["current_task"] = "Syncing Price Data"
        
        add_log(f"計畫下載 K 線歷史數據之個股總數: {total_tickers} 檔")
        
        # Default start date is 2 years ago if not provided
        if not start_date:
            start_date = "2024-01-01"
            
        add_log(f"下載天期範圍起始日: {start_date}")
        
        # Download in batches of 50 to optimize performance and prevent yfinance rate limits
        batch_size = 50
        batches = [tickers_to_sync[i:i + batch_size] for i in range(0, total_tickers, batch_size)]
        
        for batch_idx, batch in enumerate(batches):
            add_log(f"正在下載第 {batch_idx+1}/{len(batches)} 批次數據 ({len(batch)} 檔)...")
            sync_status["message"] = f"正在下載第 {batch_idx+1}/{len(batches)} 批次歷史 K 線..."
            
            try:
                # yf.download handles lists very efficiently in one call
                # group_by='column' is default, which returns a MultiIndex DataFrame
                df = yf.download(batch, start=start_date, group_by='ticker', progress=False)
                
                if df.empty:
                    add_log(f"批次 {batch_idx+1} 下載返回空值")
                    sync_status["processed_count"] += len(batch)
                    sync_status["progress"] = int((sync_status["processed_count"] / total_tickers) * 100)
                    continue
                
                prices_to_insert = []
                
                # Iterate and format
                for ticker in batch:
                    # If only one ticker was in the batch, yfinance might return a standard single Index DataFrame
                    # instead of MultiIndex. Let's handle both.
                    try:
                        if len(batch) == 1:
                            ticker_df = df
                        else:
                            if ticker not in df.columns.levels[0]:
                                continue
                            ticker_df = df[ticker]
                            
                        ticker_df = ticker_df.dropna(subset=['Close'])
                        
                        for date, row in ticker_df.iterrows():
                            # Format date to YYYY-MM-DD
                            date_str = date.strftime("%Y-%m-%d")
                            
                            prices_to_insert.append({
                                "ticker": ticker,
                                "date": date_str,
                                "open": float(row['Open']),
                                "high": float(row['High']),
                                "low": float(row['Low']),
                                "close": float(row['Close']),
                                "volume": int(row['Volume'])
                            })
                    except Exception as single_err:
                        # Skip errors for single failed tickers
                        continue
                
                if prices_to_insert:
                    insert_stock_prices(prices_to_insert)
                    add_log(f"已成功寫入 {len(prices_to_insert)} 筆 K 線記錄")
                
                sync_status["processed_count"] += len(batch)
                sync_status["progress"] = int((sync_status["processed_count"] / total_tickers) * 100)
                
            except Exception as batch_err:
                add_log(f"下載批次 {batch_idx+1} 時發生異常：{str(batch_err)}")
                sync_status["processed_count"] += len(batch)
                sync_status["progress"] = int((sync_status["processed_count"] / total_tickers) * 100)
                
            # Subtle sleep between batches to respect yfinance endpoints
            time.sleep(1)
            
        sync_status["progress"] = 100
        sync_status["message"] = "同步全部完成！"
        sync_status["current_task"] = "Completed"
        add_log("=== 市場資料同步作業圓滿完成！ ===")
        
    except Exception as e:
        sync_status["message"] = f"同步失敗：{str(e)}"
        sync_status["current_task"] = "Failed"
        add_log(f"全域錯誤：同步作業中斷。原因：{str(e)}")
        
    finally:
        sync_status["is_running"] = False

def start_data_sync(start_date=None, force_tickers=None):
    """
    Spawns the synchronizer thread in the background.
    """
    global sync_status
    if sync_status["is_running"]:
        return False, "同步任務正在執行中，無法重複啟動。"
        
    t = threading.Thread(target=sync_prices_worker, args=(start_date, force_tickers))
    t.daemon = True
    t.start()
    return True, "同步任務已在背景啟動。"

if __name__ == "__main__":
    # Test execution
    # Start and wait for it to complete in main thread
    sync_prices_worker(start_date="2025-01-01", force_tickers=["2330.TW", "^TWII"])
