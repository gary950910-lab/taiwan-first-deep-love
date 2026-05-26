import os
import pandas as pd
import yfinance as yf
from datetime import datetime

def get_stock_data(ticker, start_date, end_date):
    """
    Fetch historical stock data (OHLCV) using yfinance with a local file caching mechanism.
    
    Parameters:
    - ticker (str): The stock ticker (e.g., '2330.TW', 'AAPL').
    - start_date (str): Start date in 'YYYY-MM-DD' format.
    - end_date (str): End date in 'YYYY-MM-DD' format.
    
    Returns:
    - pd.DataFrame: Historical stock data with a DatetimeIndex and ['Open', 'High', 'Low', 'Close', 'Volume'] columns.
    """
    # Create local cache directory inside the instance folder
    cache_dir = os.path.join('instance', 'yf_cache')
    os.makedirs(cache_dir, exist_ok=True)
    
    # Generate a cache filename
    # Sanitize the ticker name to prevent folder traversal
    safe_ticker = "".join([c for c in ticker if c.isalnum() or c in ['.', '-']]).strip()
    cache_filename = f"{safe_ticker}_{start_date}_{end_date}.csv"
    cache_path = os.path.join(cache_dir, cache_filename)
    
    # Check if cache exists
    if os.path.exists(cache_path):
        try:
            print(f"Loading {ticker} from cache: {cache_path}")
            df = pd.read_csv(cache_path, parse_dates=['Date'])
            df.set_index('Date', inplace=True)
            if not df.empty:
                return df
        except Exception as e:
            print(f"Error reading cache for {ticker}: {e}. Downloading instead.")
            
    # Fetch from yfinance
    print(f"Downloading {ticker} from yfinance for range {start_date} to {end_date}")
    try:
        # Download data
        # Note: yfinance download returns a MultiIndex if single ticker is passed with group_by,
        # but standard download returns a clean DataFrame with columns like Open, High, Low, Close, etc.
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if df.empty:
            print(f"No data returned for ticker {ticker}")
            return pd.DataFrame()
            
        # Clean up columns if it has a MultiIndex (sometimes yfinance returns multi-index columns even for 1 ticker)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Ensure index is named 'Date'
        df.index.name = 'Date'
        
        # Select required columns
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        df = df[required_cols]
        
        # Save to cache
        df.to_csv(cache_path)
        print(f"Saved {ticker} to cache: {cache_path}")
        return df
        
    except Exception as e:
        print(f"Failed to fetch stock data for {ticker} from yfinance: {e}")
        return pd.DataFrame()
