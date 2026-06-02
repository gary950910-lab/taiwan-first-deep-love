import pandas as pd
import numpy as np
import json
from datetime import datetime
from backend.services.database import get_db_connection, get_price_history
from backend.services.indicators import calculate_all_indicators

def check_strategy_conditions(df: pd.DataFrame, idx: int, strategy: dict) -> bool:
    """
    Checks if strategy screening conditions are met on df.iloc[idx].
    """
    if idx < 60:  # Need enough data to warm up indicators
        return False
        
    row = df.iloc[idx]
    prev_row = df.iloc[idx - 1] if idx > 0 else None
    
    conds = strategy.get('custom_conditions', {})
    
    # 1. MACD Filters
    macd_val = row.get('macd')
    macd_sig = row.get('macd_signal')
    macd_hist = row.get('macd_histogram')
    
    if conds.get('macd_golden_cross') and macd_val is not None and macd_sig is not None:
        # MACD crosses above signal
        if prev_row is None: return False
        prev_macd = prev_row.get('macd')
        prev_sig = prev_row.get('macd_signal')
        if not (prev_macd <= prev_sig and macd_val > macd_sig):
            return False
            
    if conds.get('macd_death_cross') and macd_val is not None and macd_sig is not None:
        # MACD crosses below signal
        if prev_row is None: return False
        prev_macd = prev_row.get('macd')
        prev_sig = prev_row.get('macd_signal')
        if not (prev_macd >= prev_sig and macd_val < macd_sig):
            return False
            
    # 2. KD Filters
    kd_k = row.get('kd_k')
    kd_d = row.get('kd_d')
    
    if conds.get('kd_golden_cross') and kd_k is not None and kd_d is not None:
        # K crosses above D
        if prev_row is None: return False
        prev_k = prev_row.get('kd_k')
        prev_d = prev_row.get('kd_d')
        if not (prev_k <= prev_d and kd_k > kd_d):
            return False
            
    if conds.get('kd_death_cross') and kd_k is not None and kd_d is not None:
        # K crosses below D
        if prev_row is None: return False
        prev_k = prev_row.get('kd_k')
        prev_d = prev_row.get('kd_d')
        if not (prev_k >= prev_d and kd_k < kd_d):
            return False
            
    if conds.get('kd_overbought') and kd_k is not None:
        if not (kd_k > 80):
            return False
            
    if conds.get('kd_oversold') and kd_k is not None:
        if not (kd_k < 20):
            return False
            
    # 3. Bollinger Band Breakout
    if conds.get('bb_breakout') and row.get('bb_breakout') is not None:
        if not row.get('bb_breakout'):
            return False
            
    if conds.get('bb_above_upper') and row.get('bb_above_upper') is not None:
        if not row.get('bb_above_upper'):
            return False
            
    # 4. MA60 Bias
    ma60_bias = row.get('ma60_bias')
    if conds.get('ma_bias_active') and ma60_bias is not None:
        op = conds.get('ma_bias_op', '>')
        val = float(conds.get('ma_bias_val', 0.0))
        if op == '>' and not (ma60_bias > val):
            return False
        elif op == '<' and not (ma60_bias < val):
            return False
            
    # 5. Volume Multiple
    vol_mult = row.get('vol_multiple')
    if conds.get('vol_mult_active') and vol_mult is not None:
        val = float(conds.get('vol_mult_val', 1.5))
        if not (vol_mult >= val):
            return False
            
    # 6. MA Convergence (Entanglement)
    if conds.get('ma_entangle_active') and row.get('ma_entangled') is not None:
        if not row.get('ma_entangled'):
            return False
            
    # 7. 20-Day High
    if conds.get('high_20_day_active') and row.get('high_20_day') is not None:
        if not row.get('high_20_day'):
            return False
            
    return True

def run_single_stock_backtest(ticker: str, df: pd.DataFrame, strategy: dict, start_date: str, end_date: str, stop_loss_pct: float, take_profit_pct: float, max_hold_days: int) -> list:
    """
    Runs T+1 backtest on a single stock, returning a list of trade dictionaries.
    """
    trades = []
    if df.empty or len(df) < 60:
        return trades
        
    dates = df.index.strftime("%Y-%m-%d").tolist()
    
    idx = 0
    while idx < len(df) - 1:
        date_str = dates[idx]
        if date_str < start_date:
            idx += 1
            continue
        if date_str > end_date:
            break
            
        # Check signal on day T
        if check_strategy_conditions(df, idx, strategy):
            # Signal triggered! We buy on T+1
            entry_idx = idx + 1
            entry_date = dates[entry_idx]
            entry_price = float(df.iloc[entry_idx]['Open'])
            
            # Target TP and SL prices
            sl_price = entry_price * (1.0 - stop_loss_pct / 100.0)
            tp_price = entry_price * (1.0 + take_profit_pct / 100.0)
            
            exit_date = None
            exit_price = None
            exit_reason = None
            hold_days = 0
            
            # Check day by day starting from T+1
            for check_idx in range(entry_idx, len(df)):
                check_date = dates[check_idx]
                row = df.iloc[check_idx]
                
                low_p = float(row['Low'])
                high_p = float(row['High'])
                open_p = float(row['Open'])
                close_p = float(row['Close'])
                
                hold_days += 1
                
                # Check Stop Loss (SL)
                hit_sl = low_p <= sl_price
                # Check Take Profit (TP)
                hit_tp = high_p >= tp_price
                
                if hit_sl and hit_tp:
                    # Conservative: both hit in the same day -> Stop Loss
                    exit_date = check_date
                    exit_price = min(open_p, sl_price) # Gap down support
                    exit_reason = "Stop Loss (Same Day)"
                    break
                elif hit_sl:
                    exit_date = check_date
                    exit_price = min(open_p, sl_price)
                    exit_reason = "Stop Loss"
                    break
                elif hit_tp:
                    exit_date = check_date
                    exit_price = max(open_p, tp_price)
                    exit_reason = "Take Profit"
                    break
                elif hold_days >= max_hold_days:
                    exit_date = check_date
                    exit_price = close_p
                    exit_reason = "Max Hold Days"
                    break
                    
            if exit_date:
                ret = ((exit_price - entry_price) / entry_price) * 100.0
                trades.append({
                    "ticker": ticker,
                    "signal_date": date_str,
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "exit_date": exit_date,
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "hold_days": hold_days,
                    "return_pct": ret
                })
                
                # To prevent overlapping trades in the same ticker from a single strategy signal,
                # we fast-forward our index past the exit date.
                # Find exit index
                while idx < len(df) - 1 and dates[idx] <= exit_date:
                    idx += 1
                continue
                
        idx += 1
                    
    return trades

def run_portfolio_backtest(strategy: dict, start_date: str, end_date: str, initial_capital: float = 1000000.0, stop_loss_pct: float = 5.0, take_profit_pct: float = 10.0, max_hold_days: int = 20, max_positions: int = 10) -> dict:
    """
    Runs a portfolio simulation using all cached stock data, matching T+1 open trades.
    Includes comparison against ^TWII buy-and-hold index.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Get tickers in price database
    cursor.execute("SELECT DISTINCT ticker FROM stock_prices")
    tickers = [row['ticker'] for row in cursor.fetchall() if row['ticker'] != "^TWII"]
    
    add_conds = strategy.get('custom_conditions', {})
    
    # Pre-calculated parameters to match indicators calculation
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
    
    # 2. Get stock names map
    cursor.execute("SELECT ticker, name, industry FROM stocks")
    stocks_map = {row['ticker']: {"name": row['name'], "industry": row['industry']} for row in cursor.fetchall()}
    
    # 3. Load all stock DataFrames and compute indicators
    all_stock_dfs = {}
    
    # To compute indicators properly, we pull data from 100 days before start_date
    cursor.execute("SELECT MIN(date) FROM stock_prices")
    min_db_date = cursor.fetchone()[0]
    
    # Date formatting
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    
    for ticker in tickers:
        prices = get_price_history(ticker)
        if len(prices) < 60:
            continue
            
        pdf = pd.DataFrame(prices)
        pdf['date_dt'] = pd.to_datetime(pdf['date'])
        pdf.set_index('date_dt', inplace=True)
        # Rename standard columns to uppercase
        pdf.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
        
        # Calculate indicators
        try:
            pdf = calculate_all_indicators(pdf, indicator_params)
            all_stock_dfs[ticker] = pdf
        except Exception as ex:
            continue
            
    # Load ^TWII Index
    twii_prices = get_price_history("^TWII")
    twii_df = pd.DataFrame(twii_prices) if twii_prices else pd.DataFrame()
    if not twii_df.empty:
        twii_df['date_dt'] = pd.to_datetime(twii_df['date'])
        twii_df.set_index('date_dt', inplace=True)
        twii_df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
        
    conn.close()
    
    if not all_stock_dfs:
        return {"error": "資料庫中沒有足夠的股票價格數據。請先至同步中心更新市場資料。"}
        
    # 4. Generate all trades
    all_trades = []
    for ticker, df in all_stock_dfs.items():
        stock_trades = run_single_stock_backtest(
            ticker=ticker,
            df=df,
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_hold_days=max_hold_days
        )
        # Add stock name & industry
        for t in stock_trades:
            meta = stocks_map.get(t['ticker'], {"name": t['ticker'], "industry": "未知"})
            t['name'] = meta['name']
            t['industry'] = meta['industry']
            
            # Calculate corresponding TWII index return during the same trade period
            if not twii_df.empty:
                try:
                    entry_dt = datetime.strptime(t['entry_date'], "%Y-%m-%d")
                    exit_dt = datetime.strptime(t['exit_date'], "%Y-%m-%d")
                    
                    # Find closest dates in index
                    idx_entry_pos = twii_df.index.get_indexer([entry_dt], method='nearest')[0]
                    idx_exit_pos = twii_df.index.get_indexer([exit_dt], method='nearest')[0]
                    
                    idx_entry = twii_df.iloc[idx_entry_pos]['Open']
                    idx_exit = twii_df.iloc[idx_exit_pos]['Close']
                    
                    t['index_return_pct'] = float(((idx_exit - idx_entry) / idx_entry) * 100.0)
                    t['relative_return_pct'] = float(t['return_pct'] - t['index_return_pct'])
                except Exception:
                    t['index_return_pct'] = 0.0
                    t['relative_return_pct'] = t['return_pct']
            else:
                t['index_return_pct'] = 0.0
                t['relative_return_pct'] = t['return_pct']
                
        all_trades.extend(stock_trades)
        
    # Sort all trades by signal/entry date
    all_trades.sort(key=lambda x: x['entry_date'])
    
    # 5. Portfolio Simulation (Equal Weight)
    # We simulate day-by-day to build the equity curve
    # We find all unique trading dates in range
    all_trading_dates = sorted(list(set(
        date for ticker_df in all_stock_dfs.values() 
        for date in ticker_df.loc[start_date:end_date].index.strftime("%Y-%m-%d")
    )))
    
    portfolio_equity = []
    active_positions = [] # List of active trade dicts: {ticker, entry_date, exit_date, buy_price, size, position_value}
    cash = initial_capital
    allocation_per_trade = initial_capital / max_positions # Constant position size
    
    # Map from entry date to trades starting on that day
    trades_by_entry_date = {}
    for t in all_trades:
        entry_date = t['entry_date']
        if entry_date not in trades_by_entry_date:
            trades_by_entry_date[entry_date] = []
        trades_by_entry_date[entry_date].append(t)
        
    # Daily valuation
    for date_str in all_trading_dates:
        curr_dt = datetime.strptime(date_str, "%Y-%m-%d")
        
        # A. Check and exit closed positions
        still_active = []
        for pos in active_positions:
            if date_str >= pos['exit_date']:
                # Position exited! Get proceeds
                realised_return = pos['trade_ref']['return_pct'] / 100.0
                proceeds = pos['invested_cash'] * (1.0 + realised_return)
                cash += proceeds
            else:
                still_active.append(pos)
        active_positions = still_active
        
        # B. Enter new positions
        if date_str in trades_by_entry_date:
            todays_entries = trades_by_entry_date[date_str]
            # Shuffle or sort entries to be deterministic (e.g. by ticker)
            todays_entries.sort(key=lambda x: x['ticker'])
            
            for entry in todays_entries:
                if len(active_positions) < max_positions and cash >= allocation_per_trade:
                    # Allocate cash
                    cash -= allocation_per_trade
                    
                    active_positions.append({
                        "ticker": entry['ticker'],
                        "entry_date": entry['entry_date'],
                        "exit_date": entry['exit_date'],
                        "buy_price": entry['entry_price'],
                        "invested_cash": allocation_per_trade,
                        "trade_ref": entry
                    })
                    
        # C. Value current portfolio
        current_positions_value = 0.0
        for pos in active_positions:
            # Get close price of today to calculate current value
            ticker_df = all_stock_dfs[pos['ticker']]
            try:
                # Find closest index position
                day_pos = ticker_df.index.get_indexer([curr_dt], method='nearest')[0]
                curr_close = float(ticker_df.iloc[day_pos]['Close'])
                # Paper value change
                paper_return = (curr_close - pos['buy_price']) / pos['buy_price']
                current_positions_value += pos['invested_cash'] * (1.0 + paper_return)
            except Exception:
                current_positions_value += pos['invested_cash']
                
        total_equity = cash + current_positions_value
        portfolio_equity.append({
            "date": date_str,
            "equity": float(total_equity)
        })
        
    # 6. Benchmark Portfolio (Buy & Hold ^TWII Index)
    twii_equity = []
    if not twii_df.empty:
        try:
            # Filter TWII within range
            twii_in_range = twii_df.loc[start_date:end_date]
            if not twii_in_range.empty:
                index_start_price = float(twii_in_range.iloc[0]['Open'])
                for date, row in twii_in_range.iterrows():
                    date_str = date.strftime("%Y-%m-%d")
                    curr_close = float(row['Close'])
                    ret = (curr_close - index_start_price) / index_start_price
                    eq = initial_capital * (1.0 + ret)
                    twii_equity.append({
                        "date": date_str,
                        "equity": float(eq)
                    })
        except Exception:
            pass
            
    # If benchmark empty, align with portfolio_equity dates at constant capital
    if not twii_equity:
        twii_equity = [{"date": p['date'], "equity": initial_capital} for p in portfolio_equity]
        
    # 7. Aggregate Strategy Performance Metrics
    total_trades = len(all_trades)
    winning_trades = [t for t in all_trades if t['return_pct'] > 0]
    losing_trades = [t for t in all_trades if t['return_pct'] <= 0]
    
    win_rate = (len(winning_trades) / total_trades * 100.0) if total_trades > 0 else 0.0
    
    avg_win = np.mean([t['return_pct'] for t in winning_trades]) if winning_trades else 0.0
    avg_loss = np.mean([t['return_pct'] for t in losing_trades]) if losing_trades else 0.0
    
    pl_ratio = float(avg_win / abs(avg_loss)) if abs(avg_loss) > 0 else 0.0
    avg_hold = float(np.mean([t['hold_days'] for t in all_trades])) if all_trades else 0.0
    
    # Calculate Max Drawdown for Strategy Equity
    mdd = 0.0
    if portfolio_equity:
        eq_series = np.array([p['equity'] for p in portfolio_equity])
        peaks = np.maximum.accumulate(eq_series)
        drawdowns = (eq_series - peaks) / peaks * 100.0
        mdd = float(np.min(drawdowns))
        
    # Final Returns
    final_eq = portfolio_equity[-1]['equity'] if portfolio_equity else initial_capital
    total_return = ((final_eq - initial_capital) / initial_capital) * 100.0
    
    final_twii_eq = twii_equity[-1]['equity'] if twii_equity else initial_capital
    twii_return = ((final_twii_eq - initial_capital) / initial_capital) * 100.0
    
    excess_return = total_return - twii_return
    
    # Group trades by industry to find industry strengths
    industry_stats = {}
    for t in all_trades:
        ind = t['industry']
        if ind not in industry_stats:
            industry_stats[ind] = {"count": 0, "win_count": 0, "sum_return": 0.0}
        
        industry_stats[ind]["count"] += 1
        if t['return_pct'] > 0:
            industry_stats[ind]["win_count"] += 1
        industry_stats[ind]["sum_return"] += t['return_pct']
        
    industry_performance = []
    for ind, stats in industry_stats.items():
        industry_performance.append({
            "industry": ind,
            "trades_count": stats["count"],
            "win_rate": float(stats["win_count"] / stats["count"] * 100.0),
            "avg_return": float(stats["sum_return"] / stats["count"])
        })
        
    # Sort by avg_return descending
    industry_performance.sort(key=lambda x: x['avg_return'], reverse=True)
    
    return {
        "summary": {
            "total_trades": total_trades,
            "win_rate": float(win_rate),
            "profit_loss_ratio": float(pl_ratio),
            "avg_hold_days": float(avg_hold),
            "total_return_pct": float(total_return),
            "benchmark_return_pct": float(twii_return),
            "excess_return_pct": float(excess_return),
            "max_drawdown_pct": float(mdd),
            "final_equity": float(final_eq),
            "final_benchmark_equity": float(final_twii_eq)
        },
        "equity_curve": portfolio_equity,
        "benchmark_curve": twii_equity,
        "industry_performance": industry_performance,
        "trades": all_trades
    }
