import pandas as pd
import numpy as np

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes all required technical indicators on a stock history DataFrame.
    Assumes df contains columns: Open, High, Low, Close, Volume (case-insensitive).
    Returns a copy of the DataFrame with added indicator columns.
    """
    # Work on a copy to avoid SettingWithCopy warnings
    df = df.copy()
    
    # Normalize column names to lowercase
    col_mapping = {c: c.lower() for c in df.columns}
    df.rename(columns=col_mapping, inplace=True)
    
    # Verify required columns exist
    required = ['open', 'high', 'low', 'close', 'volume']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
            
    # Cast to float
    for col in required:
        df[col] = df[col].astype(float)
        
    # 1. Moving Averages
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma10'] = df['close'].rolling(window=10).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    
    # 2. MA60 Bias (%)
    df['ma60_bias'] = ((df['close'] - df['ma60']) / df['ma60']) * 100.0
    
    # 3. Bollinger Bands (20, 2)
    df['bb_mid'] = df['ma20']
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_mid'] + 2.0 * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - 2.0 * df['bb_std']
    
    # 4. KD (9, 3, 3)
    low_9 = df['low'].rolling(window=9).min()
    high_9 = df['high'].rolling(window=9).max()
    
    # Handle division by zero when high_9 == low_9
    denom = high_9 - low_9
    rsv = np.where(denom == 0, 50.0, ((df['close'] - low_9) / denom) * 100.0)
    
    # KD recursive calculation
    k_list = []
    d_list = []
    k_val = 50.0
    d_val = 50.0
    for val in rsv:
        if np.isnan(val):
            k_list.append(np.nan)
            d_list.append(np.nan)
        else:
            k_val = (2.0 / 3.0) * k_val + (1.0 / 3.0) * val
            d_val = (2.0 / 3.0) * d_val + (1.0 / 3.0) * k_val
            k_list.append(k_val)
            d_list.append(d_val)
            
    df['k'] = k_list
    df['d'] = d_list
    
    # 5. MACD (12, 26, 9)
    df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
    df['macd_dif'] = df['ema12'] - df['ema26']
    df['macd_dem'] = df['macd_dif'].ewm(span=9, adjust=False).mean()
    df['macd_osc'] = df['macd_dif'] - df['macd_dem']
    
    # 6. 20-day High (True/False represented as 1/0)
    # Check if today's Close or High is the highest of the last 20 trading days
    # Let's use High vs max of past 20 days Highs
    high_20 = df['high'].rolling(window=20).max()
    df['is_20d_high'] = (df['high'] >= high_20).astype(int)
    
    # 7. Volume Multiplier
    df['volume_ma5'] = df['volume'].rolling(window=5).mean()
    df['volume_ratio'] = np.where(df['volume_ma5'] == 0, 1.0, df['volume'] / df['volume_ma5'])
    
    # 8. MA Consolidation (糾結)
    # Define MA consolidation as standard deviation or spread of MA5, MA10, MA20 within a small % of their mean
    # Let's compute the spread: (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / mean * 100
    ma_min = df[['ma5', 'ma10', 'ma20']].min(axis=1)
    ma_max = df[['ma5', 'ma10', 'ma20']].max(axis=1)
    ma_mean = df[['ma5', 'ma10', 'ma20']].mean(axis=1)
    df['ma_dispersion'] = np.where(ma_mean == 0, 0.0, ((ma_max - ma_min) / ma_mean) * 100.0)
    
    return df

def clean_row_for_json(row_dict):
    """
    Cleans a dictionary containing row data to ensure it is JSON compliant.
    Converts NaN/Infinity to None (null in JSON).
    """
    cleaned = {}
    for k, v in row_dict.items():
        if pd.isna(v) or (isinstance(v, float) and (np.isinf(v) or np.isnan(v))):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned
