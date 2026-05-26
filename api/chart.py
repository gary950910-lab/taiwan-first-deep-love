from fastapi import APIRouter, HTTPException, Query
import yfinance as yf
import pandas as pd
import numpy as np
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def sanitize_value(val):
    """
    將 Pandas/Numpy 的數值安全地轉換為 Python 原生型態，並處理 NaN 與 Inf。
    """
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (float, np.floating)):
        if np.isinf(val) or np.isnan(val):
            return None
        return round(float(val), 2)
    if isinstance(val, (int, np.integer)):
        return int(val)
    return val

@router.get("/api/chart/{ticker}")
async def get_chart_data(
    ticker: str,
    period: str = Query(default="1y", description="歷史數據期間，例如：1mo, 3mo, 6mo, 1y, 2y, 5y")
):
    """
    獲取個股的歷史價格（OHLCV）與均線指標（MA5, MA20, MA60）。
    會自動判斷台股上市 (.TW) 或上櫃 (.TWO)。
    """
    ticker_upper = ticker.upper().strip()
    df = pd.DataFrame()
    resolved_ticker = ticker_upper

    # 1. 決定如何下載數據
    if "." in ticker_upper or "^" in ticker_upper:
        # 已有後綴或是指數（如 ^TWII），直接下載
        try:
            logger.info(f"Downloading directly: {ticker_upper} with period={period}")
            df = yf.Ticker(ticker_upper).history(period=period)
        except Exception as e:
            logger.error(f"Error downloading {ticker_upper}: {e}")
    else:
        # 台股代碼（通常是純數字，如 2330）
        if ticker_upper.isdigit():
            # 優先嘗試上市 (.TW)
            tw_ticker = f"{ticker_upper}.TW"
            try:
                logger.info(f"Trying listed (TW): {tw_ticker} with period={period}")
                df = yf.Ticker(tw_ticker).history(period=period)
                if not df.empty and len(df) > 5:
                    resolved_ticker = tw_ticker
                else:
                    df = pd.DataFrame() # 重置以便進行下一步
            except Exception as e:
                logger.warning(f"Error downloading {tw_ticker}: {e}")

            # 若上市無資料，嘗試上櫃 (.TWO)
            if df.empty:
                two_ticker = f"{ticker_upper}.TWO"
                try:
                    logger.info(f"Trying OTC (TWO): {two_ticker} with period={period}")
                    df = yf.Ticker(two_ticker).history(period=period)
                    if not df.empty and len(df) > 5:
                        resolved_ticker = two_ticker
                    else:
                        df = pd.DataFrame()
                except Exception as e:
                    logger.warning(f"Error downloading {two_ticker}: {e}")

        # 若都失敗，嘗試直接下載原符號（可能是美股或大盤）
        if df.empty:
            try:
                logger.info(f"Trying raw symbol: {ticker_upper} with period={period}")
                df = yf.Ticker(ticker_upper).history(period=period)
                resolved_ticker = ticker_upper
            except Exception as e:
                logger.error(f"Error downloading raw {ticker_upper}: {e}")

    # 2. 檢查數據是否為空
    if df.empty:
        raise HTTPException(
            status_code=404, 
            detail=f"無法獲取股票代號 '{ticker}' 的數據。請確認輸入代號是否正確，或該股票無交易紀錄。"
        )

    # 3. 計算技術指標 (MA5, MA20, MA60)
    try:
        df["MA5"] = df["Close"].rolling(window=5).mean()
        df["MA20"] = df["Close"].rolling(window=20).mean()
        df["MA60"] = df["Close"].rolling(window=60).mean()
    except Exception as e:
        logger.error(f"Error calculating MAs for {resolved_ticker}: {e}")

    # 4. 格式化時間索引
    df.index = df.index.strftime('%Y-%m-%d')

    # 5. 轉換為 JSON 安全格式的列表
    chart_data = []
    for idx, row in df.iterrows():
        chart_data.append({
            "time": str(idx),
            "open": sanitize_value(row.get('Open')),
            "high": sanitize_value(row.get('High')),
            "low": sanitize_value(row.get('Low')),
            "close": sanitize_value(row.get('Close')),
            "volume": sanitize_value(row.get('Volume')),
            "ma5": sanitize_value(row.get('MA5')),
            "ma20": sanitize_value(row.get('MA20')),
            "ma60": sanitize_value(row.get('MA60'))
        })

    # 獲取個股基本名稱（可選）
    return {
        "ticker": ticker_upper,
        "resolved_ticker": resolved_ticker,
        "period": period,
        "data": chart_data
    }
