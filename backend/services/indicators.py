import pandas as pd
import pandas_ta as ta
import numpy as np

def add_bollinger_bands(df: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    """Calculates Bollinger Bands and standardizes column names."""
    if df.empty or len(df) < length:
        # Fill default columns with NaN
        df['bb_lower'] = np.nan
        df['bb_mid'] = np.nan
        df['bb_upper'] = np.nan
        return df
    
    try:
        bb = df.ta.bbands(length=length, std=std)
        if bb is not None and not bb.empty:
            # Expected columns: BBL_{length}_{std}, BBM_{length}_{std}, BBU_{length}_{std}
            for col in bb.columns:
                if col.startswith("BBL"): df['bb_lower'] = bb[col]
                elif col.startswith("BBM"): df['bb_mid'] = bb[col]
                elif col.startswith("BBU"): df['bb_upper'] = bb[col]
    except Exception as e:
        df['bb_lower'] = np.nan
        df['bb_mid'] = np.nan
        df['bb_upper'] = np.nan
    return df

def add_kd(df: pd.DataFrame, k_length: int = 9, d_length: int = 3) -> pd.DataFrame:
    """Calculates KD (Stochastic) and standardizes column names."""
    if df.empty or len(df) < k_length:
        df['kd_k'] = np.nan
        df['kd_d'] = np.nan
        return df
    
    try:
        stoch = df.ta.stoch(high=df['High'], low=df['Low'], close=df['Close'], k=k_length, d=d_length, smooth_k=3)
        if stoch is not None and not stoch.empty:
            for col in stoch.columns:
                if col.startswith("STOCHk"): df['kd_k'] = stoch[col]
                elif col.startswith("STOCHd"): df['kd_d'] = stoch[col]
    except Exception as e:
        df['kd_k'] = np.nan
        df['kd_d'] = np.nan
    return df

def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Calculates MACD and standardizes column names."""
    if df.empty or len(df) < slow:
        df['macd'] = np.nan
        df['macd_histogram'] = np.nan
        df['macd_signal'] = np.nan
        return df
        
    try:
        macd = df.ta.macd(close=df['Close'], fast=fast, slow=slow, signal=signal)
        if macd is not None and not macd.empty:
            for col in macd.columns:
                if col.startswith("MACD_"): df['macd'] = macd[col]
                elif col.startswith("MACDh_"): df['macd_histogram'] = macd[col]
                elif col.startswith("MACDs_"): df['macd_signal'] = macd[col]
    except Exception as e:
        df['macd'] = np.nan
        df['macd_histogram'] = np.nan
        df['macd_signal'] = np.nan
    return df

def add_ma_bias(df: pd.DataFrame, length: int = 60) -> pd.DataFrame:
    """Calculates Moving Average Bias."""
    col_ma = f"ma{length}"
    col_bias = f"ma{length}_bias"
    
    if df.empty or len(df) < length:
        df[col_ma] = np.nan
        df[col_bias] = np.nan
        return df
        
    df[col_ma] = df['Close'].rolling(window=length).mean()
    df[col_bias] = ((df['Close'] - df[col_ma]) / df[col_ma]) * 100
    return df

def add_volume_multiple(df: pd.DataFrame, length: int = 5) -> pd.DataFrame:
    """Calculates relative volume compared to N-day moving average volume."""
    col_vol_ma = f"vol_ma{length}"
    
    if df.empty or len(df) < length:
        df[col_vol_ma] = np.nan
        df['vol_multiple'] = np.nan
        return df
        
    df[col_vol_ma] = df['Volume'].rolling(window=length).mean()
    # Avoid division by zero
    df['vol_multiple'] = np.where(df[col_vol_ma] > 0, df['Volume'] / df[col_vol_ma], 0.0)
    return df

def add_ma_entanglement(df: pd.DataFrame, lengths=[5, 10, 20, 60], threshold=2.0) -> pd.DataFrame:
    """
    Calculates Moving Average Convergence (Entanglement).
    Checks if multiple MAs are close to each other within a threshold percentage.
    """
    if df.empty or len(df) < max(lengths):
        df['ma_convergence'] = np.nan
        df['ma_entangled'] = False
        return df
        
    ma_cols = []
    for length in lengths:
        col_name = f"_tmp_ma_{length}"
        df[col_name] = df['Close'].rolling(window=length).mean()
        ma_cols.append(col_name)
        
    # Calculate standard deviation and mean across rows for these MAs
    ma_df = df[ma_cols]
    mean_ma = ma_df.mean(axis=1)
    std_ma = ma_df.std(axis=1)
    
    # Convergence ratio as std_ma / mean_ma * 100%
    df['ma_convergence'] = np.where(mean_ma > 0, (std_ma / mean_ma) * 100, np.nan)
    df['ma_entangled'] = df['ma_convergence'] < threshold
    
    # Drop temporary columns
    df.drop(columns=ma_cols, inplace=True)
    return df

def add_bb_breakout(df: pd.DataFrame) -> pd.DataFrame:
    """Determines Bollinger Band breakouts and crossovers."""
    if 'bb_upper' not in df.columns:
        df = add_bollinger_bands(df)
        
    df['bb_above_upper'] = df['Close'] > df['bb_upper']
    
    # Cross over (Close crosses above upper band today)
    prev_close = df['Close'].shift(1)
    prev_upper = df['bb_upper'].shift(1)
    df['bb_breakout'] = (df['Close'] > df['bb_upper']) & (prev_close <= prev_upper)
    return df

def add_n_day_high(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """Calculates if the today's close is a new N-day high."""
    if df.empty or len(df) < length:
        df['high_20_day'] = False
        return df
        
    rolling_max = df['Close'].rolling(window=length).max()
    df['high_20_day'] = df['Close'] == rolling_max
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
    
    # Advanced params
    ma_bias_len = params.get('ma_bias_length', 60)
    vol_mult_len = params.get('volume_multiple_length', 5)
    entangle_threshold = params.get('entangle_threshold', 2.0)
    high_n_len = params.get('high_n_length', 20)
    
    # Process
    df = add_bollinger_bands(df, length=bb_len, std=bb_std)
    df = add_kd(df, k_length=kd_k, d_length=kd_d)
    df = add_macd(df, fast=macd_fast, slow=macd_slow, signal=macd_signal)
    
    # New indicators
    df = add_ma_bias(df, length=ma_bias_len)
    df = add_volume_multiple(df, length=vol_mult_len)
    df = add_ma_entanglement(df, lengths=[5, 10, 20, 60], threshold=entangle_threshold)
    df = add_bb_breakout(df)
    df = add_n_day_high(df, length=high_n_len)
    
    return df

if __name__ == "__main__":
    # Test indicator logic with dummy data
    dates = pd.date_range(start="2026-01-01", periods=100)
    close_prices = 100.0 + np.cumsum(np.random.normal(0, 1, 100))
    high_prices = close_prices + np.abs(np.random.normal(1, 0.5, 100))
    low_prices = close_prices - np.abs(np.random.normal(1, 0.5, 100))
    open_prices = close_prices + np.random.normal(0, 0.5, 100)
    volumes = np.random.randint(1000, 5000, size=100)
    
    df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volumes
    }, index=dates)
    
    df = calculate_all_indicators(df)
    print("Columns calculated:", [c for c in df.columns if not c in ['Open', 'High', 'Low', 'Close', 'Volume']])
    print("Latest row of calculated data:\n", df.iloc[-1])
