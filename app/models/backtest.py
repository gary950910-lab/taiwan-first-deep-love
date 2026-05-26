import pandas as pd
import numpy as np
from app.models.stock import get_stock_data

class BacktestEngine:
    @staticmethod
    def calculate_indicators(df):
        """
        Calculate KD and MACD indicators for the stock DataFrame.
        """
        if df.empty or len(df) < 26:
            return df
            
        df = df.copy()
        
        # 1. Calculate KD (9, 3, 3)
        # RSV = (Close - Low_9) / (High_9 - Low_9) * 100
        low_9 = df['Low'].rolling(window=9).min()
        high_9 = df['High'].rolling(window=9).max()
        
        # Avoid division by zero
        denom = high_9 - low_9
        rsv = np.where(denom == 0, 50, (df['Close'] - low_9) / denom * 100)
        
        # Calculate K and D values using EMA
        k_values = []
        d_values = []
        current_k = 50.0
        current_d = 50.0
        
        for r in rsv:
            if np.isnan(r):
                k_values.append(np.nan)
                d_values.append(np.nan)
            else:
                current_k = (2.0 / 3.0) * current_k + (1.0 / 3.0) * r
                current_d = (2.0 / 3.0) * current_d + (1.0 / 3.0) * current_k
                k_values.append(current_k)
                d_values.append(current_d)
                
        df['K'] = k_values
        df['D'] = d_values
        
        # 2. Calculate MACD (12, 26, 9)
        ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = ema_12 - ema_26
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = 2 * (df['DIF'] - df['DEA'])
        
        return df

    @staticmethod
    def generate_signals(df, strategy='KD'):
        """
        Generate buy signals based on chosen strategy.
        - 'KD': K crosses above D (KD Golden Cross)
        - 'MACD': DIF crosses above DEA (MACD Golden Cross)
        - 'BuyHold': Buy on first available day
        """
        if df.empty:
            return df
            
        df = df.copy()
        df['Signal'] = 0
        
        if strategy == 'KD':
            # K crosses above D
            k_prev = df['K'].shift(1)
            d_prev = df['D'].shift(1)
            df.loc[(k_prev < d_prev) & (df['K'] > df['D']), 'Signal'] = 1
            
        elif strategy == 'MACD':
            # DIF crosses above DEA
            dif_prev = df['DIF'].shift(1)
            dea_prev = df['DBA'].shift(1) if 'DBA' in df else df['DEA'].shift(1)
            df.loc[(dif_prev < dea_prev) & (df['DIF'] > df['DEA']), 'Signal'] = 1
            
        elif strategy == 'BuyHold':
            df.iloc[0, df.columns.get_loc('Signal')] = 1
            
        return df

    @classmethod
    def run_backtest(cls, ticker, start_date, end_date, strategy='KD', stop_loss_pct=5.0, take_profit_pct=10.0):
        """
        Run the T+1 opening entry backtesting engine with stop loss and take profit.
        
        Parameters:
        - ticker (str): Stock code
        - start_date (str): Start date
        - end_date (str): End date
        - strategy (str): 'KD', 'MACD', or 'BuyHold'
        - stop_loss_pct (float): Stop loss percentage (e.g. 5.0)
        - take_profit_pct (float): Take profit percentage (e.g. 10.0)
        
        Returns:
        - dict: Backtesting results including performance metrics and trade details
        """
        # Fetch daily OHLCV
        raw_df = get_stock_data(ticker, start_date, end_date)
        if raw_df.empty:
            return {
                'success': False,
                'error': f"無法下載 {ticker} 的歷史數據，或該期間無交易數據。"
            }
            
        # Calculate technical indicators
        df_indicators = cls.calculate_indicators(raw_df)
        
        # Generate entry signals
        df = cls.generate_signals(df_indicators, strategy)
        
        trades = []
        in_position = False
        entry_price = 0.0
        entry_date = None
        sl_price = 0.0
        tp_price = 0.0
        
        # Track daily portfolio value for equity curve & MDD calculation
        initial_capital = 1000000.0 # $1,000,000 starting cash
        cash = initial_capital
        shares = 0.0
        daily_equity = []
        
        # Iterate row by row (T+1 Entry, Daily Stop/Profit check)
        # We start check from index 0
        dates = df.index
        for i in range(len(df)):
            date_str = dates[i].strftime('%Y-%m-%d')
            row = df.iloc[i]
            
            # Extract daily OHLC
            daily_open = float(row['Open'])
            daily_high = float(row['High'])
            daily_low = float(row['Low'])
            daily_close = float(row['Close'])
            
            # --- Check Exit Conditions first if in position ---
            trade_exited_today = False
            if in_position:
                exit_triggered = False
                exit_price = 0.0
                exit_reason = ""
                
                # Case 1: Open is already below Stop Loss (Gap Down)
                if daily_open <= sl_price:
                    exit_triggered = True
                    exit_price = daily_open
                    exit_reason = "開盤跳空停損"
                # Case 2: Open is already above Take Profit (Gap Up)
                elif daily_open >= tp_price:
                    exit_triggered = True
                    exit_price = daily_open
                    exit_reason = "開盤跳空停利"
                # Case 3: Low crosses below Stop Loss
                elif daily_low <= sl_price:
                    exit_triggered = True
                    exit_price = sl_price
                    exit_reason = "觸及停損"
                # Case 4: High crosses above Take Profit
                elif daily_high >= tp_price:
                    exit_triggered = True
                    exit_price = tp_price
                    exit_reason = "觸及停利"
                # Case 5: Last trading day force Flat
                elif i == len(df) - 1:
                    exit_triggered = True
                    exit_price = daily_close
                    exit_reason = "期末強制平倉"
                
                if exit_triggered:
                    # Execute Exit Trade
                    gross_return = (exit_price - entry_price) / entry_price
                    cash = shares * exit_price
                    shares = 0.0
                    in_position = False
                    trade_exited_today = True
                    
                    trades.append({
                        'type': 'Exit',
                        'date': date_str,
                        'price': round(exit_price, 2),
                        'reason': exit_reason,
                        'entry_date': entry_date,
                        'entry_price': round(entry_price, 2),
                        'return_pct': round(gross_return * 100, 2),
                        'profit_loss': round(shares * (exit_price - entry_price), 2)
                    })
            
            # --- Check Entry Conditions if not in position ---
            # Wait, T+1 entry logic: if previous day (i-1) had a signal, we buy today at Open!
            if not in_position and not trade_exited_today and i > 0:
                prev_row = df.iloc[i-1]
                if int(prev_row['Signal']) == 1:
                    # Buy today at Open
                    entry_price = daily_open
                    entry_date = dates[i].strftime('%Y-%m-%d')
                    in_position = True
                    
                    # Calculate Stop Loss and Take Profit levels
                    sl_price = entry_price * (1.0 - stop_loss_pct / 100.0)
                    tp_price = entry_price * (1.0 + take_profit_pct / 100.0)
                    
                    shares = cash / entry_price
                    cash = 0.0
                    
                    trades.append({
                        'type': 'Entry',
                        'date': entry_date,
                        'price': round(entry_price, 2),
                        'reason': 'T+1 開盤進場',
                        'sl_price': round(sl_price, 2),
                        'tp_price': round(tp_price, 2)
                    })
                    
                    # Recheck exit conditions on the entry day itself! (conservative check)
                    if daily_low <= sl_price or daily_high >= tp_price:
                        # Exit triggered on same day
                        exit_price = sl_price if daily_low <= sl_price else tp_price
                        exit_reason = "觸及停損 (同日)" if daily_low <= sl_price else "觸及停利 (同日)"
                        gross_return = (exit_price - entry_price) / entry_price
                        cash = shares * exit_price
                        shares = 0.0
                        in_position = False
                        
                        trades.append({
                            'type': 'Exit',
                            'date': date_str,
                            'price': round(exit_price, 2),
                            'reason': exit_reason,
                            'entry_date': entry_date,
                            'entry_price': round(entry_price, 2),
                            'return_pct': round(gross_return * 100, 2),
                            'profit_loss': round(shares * (exit_price - entry_price), 2)
                        })
            
            # --- Track Daily Portfolio Value (Equity) ---
            if in_position:
                current_equity = shares * daily_close
            else:
                current_equity = cash
                
            daily_equity.append({
                'date': date_str,
                'equity': current_equity,
                'close': daily_close
            })
            
        # --- Calculate Performance Metrics ---
        # Get list of completed trades (Exits)
        completed_trades = [t for t in trades if t['type'] == 'Exit']
        total_trades_count = len(completed_trades)
        
        if total_trades_count > 0:
            win_trades = [t for t in completed_trades if t['return_pct'] > 0]
            loss_trades = [t for t in completed_trades if t['return_pct'] <= 0]
            
            win_rate = (len(win_trades) / total_trades_count) * 100
            
            avg_win = np.mean([t['return_pct'] for t in win_trades]) if win_trades else 0.0
            avg_loss = np.mean([t['return_pct'] for t in loss_trades]) if loss_trades else 0.0
            
            # Avoid division by zero in profit-loss ratio
            profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf') if avg_win > 0 else 0.0
            
            total_return_pct = ((daily_equity[-1]['equity'] - initial_capital) / initial_capital) * 100
        else:
            win_rate = 0.0
            profit_loss_ratio = 0.0
            total_return_pct = 0.0
            
        # --- Calculate Max Drawdown (MDD) ---
        equity_series = [e['equity'] for e in daily_equity]
        peaks = np.maximum.accumulate(equity_series)
        drawdowns = (peaks - equity_series) / peaks * 100
        max_drawdown = np.max(drawdowns)
        
        # --- Prepare Chart Data ---
        chart_dates = [e['date'] for e in daily_equity]
        chart_equity = [round(e['equity'], 2) for e in daily_equity]
        # Normalize stock price to compare with equity starting from $1,000,000
        first_close = daily_equity[0]['close']
        chart_stock_return = [round((e['close'] - first_close) / first_close * 100, 2) for e in daily_equity]
        chart_portfolio_return = [round((e['equity'] - initial_capital) / initial_capital * 100, 2) for e in daily_equity]
        
        # Make a summary of trades
        formatted_trades = []
        for t in trades:
            formatted_trades.append(t)

        return {
            'success': True,
            'ticker': ticker,
            'strategy': strategy,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'metrics': {
                'total_return_pct': float(round(total_return_pct, 2)),
                'win_rate_pct': float(round(win_rate, 2)),
                'profit_loss_ratio': float(round(profit_loss_ratio, 2)) if profit_loss_ratio != float('inf') else 'Infinity',
                'max_drawdown_pct': float(round(max_drawdown, 2)),
                'total_trades': int(total_trades_count),
                'initial_capital': float(initial_capital),
                'final_capital': float(round(daily_equity[-1]['equity'], 2))
            },
            'chart_data': {
                'dates': chart_dates,
                'equity': chart_equity,
                'portfolio_return_pct': chart_portfolio_return,
                'stock_return_pct': chart_stock_return
            },
            'trades': formatted_trades
        }
