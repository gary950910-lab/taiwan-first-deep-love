import pandas as pd
import pandas_ta as ta

def add_bollinger_bands(df: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    """Calculates Bollinger Bands and standardizes column names."""
    if df.empty:
        return df
    
    bb = df.ta.bbands(length=length, std=std)
    if bb is not None and not bb.empty:
        # Expected columns: BBL_{length}_{std}, BBM_{length}_{std}, BBU_{length}_{std}
        for col in bb.columns:
            if col.startswith("BBL"): df['bb_lower'] = bb[col]
            elif col.startswith("BBM"): df['bb_mid'] = bb[col]
            elif col.startswith("BBU"): df['bb_upper'] = bb[col]
    return df

def add_kd(df: pd.DataFrame, k_length: int = 9, d_length: int = 3) -> pd.DataFrame:
    """Calculates KD (Stochastic) and standardizes column names."""
    if df.empty:
        return df
    
    stoch = df.ta.stoch(high=df['High'], low=df['Low'], close=df['Close'], k=k_length, d=d_length, smooth_k=3)
    if stoch is not None and not stoch.empty:
        for col in stoch.columns:
            if col.startswith("STOCHk"): df['kd_k'] = stoch[col]
            elif col.startswith("STOCHd"): df['kd_d'] = stoch[col]
    return df

def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Calculates MACD and standardizes column names."""
    if df.empty:
        return df
        
    macd = df.ta.macd(close=df['Close'], fast=fast, slow=slow, signal=signal)
    if macd is not None and not macd.empty:
        for col in macd.columns:
            if col.startswith("MACD_"): df['macd'] = macd[col]
            elif col.startswith("MACDh_"): df['macd_histogram'] = macd[col]
            elif col.startswith("MACDs_"): df['macd_signal'] = macd[col]
    return df

def calculate_all_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    """Convenience function to calculate all requested indicators."""
    if params is None:
        params = {}
    
    # Extract params with defaults
    bb_len = params.get('bb_length', 20)
    bb_std = params.get('bb_std', 2.0)
    kd_k = params.get('kd_k_length', 9)
    kd_d = params.get('kd_d_length', 3)
    macd_fast = params.get('macd_fast', 12)
    macd_slow = params.get('macd_slow', 26)
    macd_signal = params.get('macd_signal', 9)
    
    df = add_bollinger_bands(df, length=bb_len, std=bb_std)
    df = add_kd(df, k_length=kd_k, d_length=kd_d)
    df = add_macd(df, fast=macd_fast, slow=macd_slow, signal=macd_signal)
    
    return df
