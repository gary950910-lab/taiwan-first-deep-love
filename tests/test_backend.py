import unittest
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.database import init_db, get_db_connection
from backend.indicators import compute_indicators, clean_row_for_json
from backend.screener import check_filters
from backend.backtester import run_backtest_simulation

class TestBackend(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Initialize DB
        init_db()
        
    def test_database_connection(self):
        """Test database connection and tables existence."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        self.assertIn('stocks', tables)
        self.assertIn('screening_sessions', tables)
        self.assertIn('screening_results', tables)
        conn.close()
        
    def test_indicator_calculations(self):
        """Test indicator formulas on mock OHLCV dataframe."""
        # Generate 70 days of mock rising data
        dates = pd.date_range(start="2026-01-01", periods=70, freq="D")
        np.random.seed(42)
        
        # Start at 100, rise slowly
        close_prices = 100.0 + np.cumsum(np.random.normal(0.5, 1.0, 70))
        open_prices = close_prices - np.random.uniform(-0.5, 0.5, 70)
        high_prices = np.maximum(open_prices, close_prices) + np.random.uniform(0, 1.0, 70)
        low_prices = np.minimum(open_prices, close_prices) - np.random.uniform(0, 1.0, 70)
        volumes = np.random.randint(1000, 5000, 70)
        
        df = pd.DataFrame({
            'Open': open_prices,
            'High': high_prices,
            'Low': low_prices,
            'Close': close_prices,
            'Volume': volumes
        }, index=dates)
        
        # Calculate indicators
        res = compute_indicators(df)
        
        # Verify columns exist
        expected_cols = [
            'ma5', 'ma10', 'ma20', 'ma60', 'ma60_bias', 
            'bb_upper', 'bb_mid', 'bb_lower', 'k', 'd', 
            'macd_dif', 'macd_dem', 'macd_osc', 'is_20d_high', 
            'volume_ratio', 'ma_dispersion'
        ]
        for col in expected_cols:
            self.assertIn(col, res.columns)
            
        # Ensure latest row has non-null calculated indicators (since index > 60)
        latest = res.iloc[-1].to_dict()
        for col in expected_cols:
            self.assertIsNotNone(latest[col])
            self.assertFalse(np.isnan(latest[col]), f"{col} is NaN at index -1")
            
    def test_filter_checks(self):
        """Test checking screening conditions on indicator rows."""
        latest = {
            'close': 110.0,
            'ma60_bias': 5.0,
            'bb_upper': 105.0,
            'bb_lower': 95.0,
            'k': 82.0,
            'd': 78.0,
            'macd_dif': 2.5,
            'macd_dem': 2.0,
            'macd_osc': 0.5,
            'is_20d_high': 1,
            'volume_ratio': 1.8,
            'ma_dispersion': 2.1
        }
        
        prev = {
            'close': 104.0,
            'bb_upper': 104.5,
            'k': 76.0,
            'd': 77.0,
            'macd_dif': 2.2,
            'macd_dem': 1.9
        }
        
        # Filter that matches
        filters_match = {
            'ma60_bias_min': 0.0,
            'ma60_bias_max': 10.0,
            'bb_break_upper': True, # close 110 > bb_upper 105 and prev close 104 <= bb_upper 104.5
            'kd_k_min': 80.0,
            'kd_cross_up': True, # k 82 > d 78 and prev k 76 <= d 77
            'macd_osc_positive': True,
            'is_20d_high': True,
            'volume_mult_min': 1.5,
            'ma_consolidation': True,
            'ma_consolidation_threshold': 3.0
        }
        
        self.assertTrue(check_filters(latest, prev, filters_match))
        
        # Filter that fails (e.g. KD K is too low)
        filters_fail = {
            'kd_k_max': 50.0
        }
        self.assertFalse(check_filters(latest, prev, filters_fail))
        
    def test_backtesting_simulation(self):
        """Test running backtest engine against mock session."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert a mock stock in stocks table (TSMC 2330)
        cursor.execute("INSERT OR REPLACE INTO stocks (symbol, name, market, industry, updated_at) VALUES (?, ?, ?, ?, ?)",
                       ('2330', '台積電', 'Listed', '半導體業', datetime.now().isoformat()))
        
        # Create a mock session
        timestamp = (datetime.now() - timedelta(days=15)).isoformat()
        cursor.execute("INSERT INTO screening_sessions (timestamp, scope, filters_json, matched_count) VALUES (?, ?, ?, ?)",
                       (timestamp, 'Listed', '{}', 1))
        session_id = cursor.lastrowid
        
        # Create mock result for that session
        mock_indicators = {
            'close': 500.0,
            'ma60_bias': 2.0
        }
        cursor.execute("INSERT INTO screening_results (session_id, symbol, name, close_price, industry, indicators_json) VALUES (?, ?, ?, ?, ?, ?)",
                       (session_id, '2330', '台積電', 500.0, '半導體業', json.dumps(mock_indicators)))
        conn.commit()
        conn.close()
        
        # Run backtest for session
        res = run_backtest_simulation(session_id, stop_loss_pct=5.0, take_profit_pct=10.0, max_holding_days=10)
        
        self.assertEqual(res['session_id'], session_id)
        self.assertIn('total_trades', res)
        self.assertIn('trades', res)
        self.assertIn('equity_curve', res)
        
        # Clean up mock session
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM screening_sessions WHERE id = ?", (session_id,))
        cursor.execute("DELETE FROM screening_results WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

if __name__ == '__main__':
    unittest.main()
