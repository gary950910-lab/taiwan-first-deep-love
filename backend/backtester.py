import json
from datetime import datetime, date
import pandas as pd
import numpy as np
import yfinance as yf
from backend.database import get_db_connection
from backend.screener import fetch_stock_data

def run_backtest_simulation(session_id: int, stop_loss_pct: float, take_profit_pct: float, max_holding_days: int = 60) -> dict:
    """
    Simulates trading for all stocks in a screening session starting from T+1.
    Calculates individual trade returns and aggregates metrics, including the strategy equity curve vs ^TWII.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch session details
    cursor.execute("SELECT timestamp, scope, filters_json FROM screening_sessions WHERE id = ?", (session_id,))
    session_row = cursor.fetchone()
    if not session_row:
        conn.close()
        raise ValueError(f"Session ID {session_id} not found")
        
    session = dict(session_row)
    # Parse session date (we only need the date part)
    session_dt = datetime.fromisoformat(session['timestamp'])
    session_date = session_dt.date()
    
    # 2. Fetch screening results (stocks)
    cursor.execute("SELECT symbol, name, close_price, industry FROM screening_results WHERE session_id = ?", (session_id,))
    stock_rows = cursor.fetchall()
    stocks = [dict(row) for row in stock_rows]
    conn.close()
    
    if not stocks:
        return {
            'session_id': session_id,
            'session_date': session_date.isoformat(),
            'total_trades': 0,
            'win_rate': 0.0,
            'avg_return': 0.0,
            'benchmark_avg_return': 0.0,
            'profit_loss_ratio': 0.0,
            'strategy_mdd': 0.0,
            'trades': [],
            'equity_curve': []
        }
        
    # 3. Fetch ^TWII benchmark history
    twii_df = fetch_stock_data("^TWII")
    if twii_df is not None:
        # Normalize index to date
        twii_df.index = pd.to_datetime(twii_df.index).date
        
    trade_results = []
    
    # We will gather daily price paths for all trades to build the portfolio equity curve.
    # To do this, we collect daily returns/prices for each stock.
    all_trade_daily_values = {}
    
    # Track the global date range of the backtest
    all_trading_days = set()
    
    # 4. Simulate each stock
    for stock in stocks:
        symbol = stock['symbol']
        name = stock['name']
        market = "OTC" if symbol.startswith(('3', '5', '6', '8')) and len(symbol) == 4 else "Listed" # Simple heuristic or we lookup from DB
        
        # Let's get the market type from the DB if possible, otherwise guess. Let's lookup from stocks table:
        conn_check = get_db_connection()
        c_check = conn_check.cursor()
        c_check.execute("SELECT market FROM stocks WHERE symbol = ?", (symbol,))
        m_row = c_check.fetchone()
        conn_check.close()
        if m_row:
            market = m_row['market']
            
        yf_symbol = f"{symbol}.TW" if market == "Listed" else f"{symbol}.TWO"
        
        df = fetch_stock_data(yf_symbol)
        if df is None or df.empty:
            continue
            
        # Normalize column names to lowercase and index to date
        df = df.copy()
        df.rename(columns={c: c.lower() for c in df.columns}, inplace=True)
        df.index = pd.to_datetime(df.index).date
        
        # Filter dates strictly greater than selection date
        sub_df = df[df.index > session_date]
        if sub_df.empty:
            continue
            
        # T+1 is the first row of sub_df
        entry_date = sub_df.index[0]
        entry_price = float(sub_df.iloc[0]['open'])
        
        if entry_price <= 0:
            continue
            
        # Determine exit conditions
        stop_loss_price = entry_price * (1.0 - (stop_loss_pct / 100.0))
        take_profit_price = entry_price * (1.0 + (take_profit_pct / 100.0))
        
        exit_date = None
        exit_price = None
        exit_reason = "Holding Limit"
        max_drawdown = 0.0
        
        # We hold at most max_holding_days rows of trading data
        holding_df = sub_df.iloc[:max_holding_days]
        
        # Track daily value for this trade (starting with 1.0 at entry open)
        daily_values = []
        
        for idx, (t_date, row) in enumerate(holding_df.iterrows()):
            t_open = float(row['open'])
            t_high = float(row['high'])
            t_low = float(row['low'])
            t_close = float(row['close'])
            
            all_trading_days.add(t_date)
            
            # Check for stop-loss and take-profit on day t
            # First check if stop-loss is hit
            if t_low <= stop_loss_price and t_high >= take_profit_price:
                # Both hit: conservatively assume SL hit first
                exit_date = t_date
                # If opening price is already below SL, exit at Open
                exit_price = min(t_open, stop_loss_price)
                exit_reason = "Stop Loss"
                
                # Calculate final drawdown before exit
                day_mdd = ((t_low - entry_price) / entry_price) * 100.0
                max_drawdown = min(max_drawdown, day_mdd)
                
                # Trade ends today
                daily_values.append((t_date, exit_price / entry_price))
                break
            elif t_low <= stop_loss_price:
                exit_date = t_date
                exit_price = min(t_open, stop_loss_price)
                exit_reason = "Stop Loss"
                
                day_mdd = ((t_low - entry_price) / entry_price) * 100.0
                max_drawdown = min(max_drawdown, day_mdd)
                
                daily_values.append((t_date, exit_price / entry_price))
                break
            elif t_high >= take_profit_price:
                exit_date = t_date
                exit_price = max(t_open, take_profit_price)
                exit_reason = "Take Profit"
                
                day_mdd = ((t_low - entry_price) / entry_price) * 100.0
                max_drawdown = min(max_drawdown, day_mdd)
                
                daily_values.append((t_date, exit_price / entry_price))
                break
                
            # If not hit, update max drawdown of the day
            day_mdd = ((t_low - entry_price) / entry_price) * 100.0
            max_drawdown = min(max_drawdown, day_mdd)
            
            # Position is still open at the end of the day, record value using close price
            daily_values.append((t_date, t_close / entry_price))
            
        # If loop finished without hitting SL/TP, exit at the close of the final day
        if exit_date is None:
            final_row = holding_df.iloc[-1]
            exit_date = holding_df.index[-1]
            exit_price = float(final_row['close'])
            exit_reason = "Holding Limit"
            
        # Calculate returns
        trade_return = ((exit_price - entry_price) / entry_price) * 100.0
        
        # Calculate benchmark return for this specific trade's period
        benchmark_return = 0.0
        if twii_df is not None:
            # Find closest entry date in twii
            twii_sub = twii_df[twii_df.index >= entry_date]
            if not twii_sub.empty:
                twii_entry_open = float(twii_sub.iloc[0]['Open'])
                # Find exit date in twii
                twii_exit_sub = twii_df[twii_df.index <= exit_date]
                if not twii_exit_sub.empty and twii_entry_open > 0:
                    twii_exit_close = float(twii_exit_sub.iloc[-1]['Close'])
                    benchmark_return = ((twii_exit_close - twii_entry_open) / twii_entry_open) * 100.0
                    
        trade_results.append({
            'symbol': symbol,
            'name': name,
            'industry': stock.get('industry', ''),
            'entry_date': entry_date.isoformat(),
            'entry_price': round(entry_price, 2),
            'exit_date': exit_date.isoformat(),
            'exit_price': round(exit_price, 2),
            'return_pct': round(trade_return, 2),
            'benchmark_return_pct': round(benchmark_return, 2),
            'exit_reason': exit_reason,
            'max_drawdown_pct': round(max_drawdown, 2)
        })
        
        # Save daily values for equity curve
        # We extend the daily value of the trade to the end of the simulation period.
        # Once closed, its value is fixed at (exit_price / entry_price)
        all_trade_daily_values[symbol] = {
            'values': dict(daily_values),
            'final_ratio': exit_price / entry_price
        }
        
    if not trade_results:
        return {
            'session_id': session_id,
            'session_date': session_date.isoformat(),
            'total_trades': 0,
            'win_rate': 0.0,
            'avg_return': 0.0,
            'benchmark_avg_return': 0.0,
            'profit_loss_ratio': 0.0,
            'strategy_mdd': 0.0,
            'trades': [],
            'equity_curve': []
        }
        
    # 5. Compute Portfolio Equity Curve
    sorted_trading_days = sorted(list(all_trading_days))
    portfolio_equity = []
    benchmark_equity = []
    
    # Initialize benchmark index value at 100
    twii_base_value = None
    
    for t_date in sorted_trading_days:
        # Strategy Equity Calculation
        # Sum of the value ratio of all stocks (each starts with 1/N weight)
        total_ratio = 0.0
        for symbol, data in all_trade_daily_values.items():
            vals = data['values']
            if t_date in vals:
                # Still holding or hit today
                total_ratio += vals[t_date]
            else:
                # Trade is either not yet started or already closed
                # If not yet started (t_date is before entry), value is 1.0 (cash)
                # If already closed (t_date is after exit), value is final_ratio (cash)
                # Let's check which one:
                # Since all trades enter on T+1 (the same day), they all start on the first trading day.
                # So if t_date is not in vals, it must be because it already closed.
                total_ratio += data['final_ratio']
                
        # Normalized portfolio value (starts around 100)
        port_val = (total_ratio / len(stocks)) * 100.0
        portfolio_equity.append({
            'date': t_date.isoformat(),
            'value': round(port_val, 2)
        })
        
        # Benchmark Equity Calculation using ^TWII close
        if twii_df is not None and t_date in twii_df.index:
            twii_close = float(twii_df.loc[t_date, 'Close'])
            if twii_base_value is None:
                # Set base to the open of the entry day if possible
                first_trading_day = sorted_trading_days[0]
                twii_entry_sub = twii_df[twii_df.index >= first_trading_day]
                if not twii_entry_sub.empty:
                    twii_base_value = float(twii_entry_sub.iloc[0]['Open'])
                else:
                    twii_base_value = twii_close
                    
            if twii_base_value > 0:
                bench_val = (twii_close / twii_base_value) * 100.0
                benchmark_equity.append({
                    'date': t_date.isoformat(),
                    'value': round(bench_val, 2)
                })
        else:
            # If TWII data is missing on this specific day, use the previous value
            prev_bench_val = benchmark_equity[-1]['value'] if benchmark_equity else 100.0
            benchmark_equity.append({
                'date': t_date.isoformat(),
                'value': prev_bench_val
            })
            
    # Calculate Strategy Max Drawdown
    peak = 100.0
    strategy_mdd = 0.0
    for eq in portfolio_equity:
        val = eq['value']
        if val > peak:
            peak = val
        dd = ((val - peak) / peak) * 100.0
        if dd < strategy_mdd:
            strategy_mdd = dd
            
    # 6. Aggregate performance metrics
    total_trades = len(trade_results)
    winning_trades = [t for t in trade_results if t['return_pct'] > 0]
    losing_trades = [t for t in trade_results if t['return_pct'] < 0]
    
    win_rate = (len(winning_trades) / total_trades) * 100.0 if total_trades > 0 else 0.0
    avg_return = np.mean([t['return_pct'] for t in trade_results]) if total_trades > 0 else 0.0
    bench_avg_return = np.mean([t['benchmark_return_pct'] for t in trade_results]) if total_trades > 0 else 0.0
    
    avg_win = np.mean([t['return_pct'] for t in winning_trades]) if winning_trades else 0.0
    avg_loss = np.mean([t['return_pct'] for t in losing_trades]) if losing_trades else 0.0
    
    # Profit/Loss Ratio: average win / average loss (absolute value)
    profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else (avg_win if avg_win > 0 else 0.0)
    
    # Combine strategy and benchmark curves into a single structure
    equity_curve = []
    for idx, eq in enumerate(portfolio_equity):
        t_date = eq['date']
        port_val = eq['value']
        bench_val = benchmark_equity[idx]['value'] if idx < len(benchmark_equity) else 100.0
        equity_curve.append({
            'date': t_date,
            'strategy': port_val,
            'benchmark': bench_val
        })
        
    return {
        'session_id': session_id,
        'session_date': session_date.isoformat(),
        'total_trades': total_trades,
        'win_rate': round(win_rate, 2),
        'avg_return': round(avg_return, 2),
        'benchmark_avg_return': round(bench_avg_return, 2),
        'profit_loss_ratio': round(profit_loss_ratio, 2),
        'strategy_mdd': round(strategy_mdd, 2),
        'trades': trade_results,
        'equity_curve': equity_curve
    }
