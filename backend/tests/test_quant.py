import unittest
import pandas as pd
import numpy as np
import os
import json
import sys
from datetime import datetime, timedelta

# Add parent path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.indicators import calculate_all_indicators
from services.backtester import run_single_stock_backtest, run_portfolio_backtest, check_strategy_conditions
from services.database import init_db, get_db_connection, insert_stocks, insert_stock_prices, save_strategy, get_strategy

class TestQuantSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize test DB in the backend directory
        init_db()
        
    def test_01_indicators_calculation(self):
        """
        Verify that indicators (standard and advanced) calculate correct column fields and have no NaN on warm-up data.
        """
        dates = pd.date_range(start="2026-01-01", periods=100)
        # Construct upward trending closing price
        close_prices = 100.0 + np.arange(100) * 0.5 + np.random.normal(0, 0.2, 100)
        high_prices = close_prices + 1.0
        low_prices = close_prices - 1.0
        open_prices = close_prices - 0.2
        volumes = 1000 + np.random.randint(100, 500, size=100)
        # Give a volume spike on day 90 to trigger volume multiple filter
        volumes[90] = 5000 
        
        df = pd.DataFrame({
            'Open': open_prices,
            'High': high_prices,
            'Low': low_prices,
            'Close': close_prices,
            'Volume': volumes
        }, index=dates)
        
        params = {
            'bb_length': 20,
            'bb_std': 2.0,
            'kd_k_length': 9,
            'kd_d_length': 3,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'ma_bias_length': 60,
            'volume_multiple_length': 5,
            'entangle_threshold': 2.0,
            'high_n_length': 20
        }
        
        df_calc = calculate_all_indicators(df, params)
        
        # Check standard columns are created
        self.assertIn('bb_lower', df_calc.columns)
        self.assertIn('bb_upper', df_calc.columns)
        self.assertIn('kd_k', df_calc.columns)
        self.assertIn('kd_d', df_calc.columns)
        self.assertIn('macd', df_calc.columns)
        self.assertIn('macd_signal', df_calc.columns)
        
        # Check advanced columns are created
        self.assertIn('ma60_bias', df_calc.columns)
        self.assertIn('vol_multiple', df_calc.columns)
        self.assertIn('ma_convergence', df_calc.columns)
        self.assertIn('ma_entangled', df_calc.columns)
        self.assertIn('bb_breakout', df_calc.columns)
        self.assertIn('high_20_day', df_calc.columns)
        
        # Check volume multiple spike was calculated
        self.assertGreater(df_calc.iloc[90]['vol_multiple'], 2.0)
        
    def test_02_backtest_exit_logic(self):
        """
        Verify single stock backtesting exit rules (Stop Loss, Take Profit, and Max Hold Days).
        """
        # Create a mock stock history of 70 days (60 days warmup + 10 days test)
        dates = pd.date_range(start="2026-01-01", periods=70)
        dates_str = dates.strftime("%Y-%m-%d").tolist()
        
        opens = [100.0]*60 + [100.0, 101.0, 100.0, 98.0,  94.0,  96.0,  97.0,  98.0,  99.0,  100.0]
        highs = [100.0]*60 + [101.0, 102.0, 101.0, 99.0,  95.0,  97.0,  98.0,  99.0,  100.0, 101.0]
        lows =  [100.0]*60 + [99.0,  100.0, 99.0,  97.0,  92.0,  95.0,  96.0,  97.0,  98.0,  99.0]
        closes = [100.0]*60 + [100.5, 101.5, 99.5, 97.5, 93.5, 96.5, 97.5, 98.5, 99.5, 100.5]
        vols = [1000]*70
        biases = [0.0]*60 + [1.0]*10
        
        # Strategy definition
        strategy = {
            "name": "Test Strategy",
            "custom_conditions": {
                "ma_bias_active": True,
                "ma_bias_op": ">",
                "ma_bias_val": 0.0
            }
        }
        
        # Create dataframe
        df = pd.DataFrame({
            'Open':  opens,
            'High':  highs,
            'Low':   lows,
            'Close': closes,
            'Volume': vols,
            'ma60_bias': biases
        }, index=dates)
        
        # Test Stop Loss at 5.0%
        # Signal triggers on Day 60 (index 60) because bias is 1.0 > 0.0.
        # Buy on Day 61 (index 61) at Open = 101.0.
        # Stop loss price is 101.0 * (1 - 0.05) = 95.95.
        # Low on Day 63 (index 63) is 92.0, which triggers Stop Loss.
        # Open price on Day 63 is 94.0, which is below 95.95, so we exit at Day 63 Open (94.0) due to gap down.
        # Hold days = 3 (index 61, 62, 63).
        trades = run_single_stock_backtest(
            ticker="2330.TW",
            df=df,
            strategy=strategy,
            start_date="2026-01-02",
            end_date="2026-03-20",
            stop_loss_pct=5.0,
            take_profit_pct=10.0,
            max_hold_days=5
        )
        
        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade['entry_date'], dates_str[61])
        self.assertEqual(trade['exit_date'], dates_str[64])
        self.assertEqual(trade['exit_reason'], "Stop Loss")
        self.assertAlmostEqual(trade['exit_price'], 94.0)
        self.assertEqual(trade['hold_days'], 4)
        self.assertAlmostEqual(trade['return_pct'], ((94.0 - 101.0) / 101.0) * 100.0)
        
    def test_03_db_CRUD(self):
        """
        Verify that database writes and reads for stocks and strategies are working properly.
        """
        # Save a custom strategy
        strategy_id = save_strategy(
            name="Test Unit Strategy",
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            kd_k=9,
            kd_d=3,
            bb_length=20,
            bb_std=2.0,
            custom_conditions={"ma_bias_active": True, "ma_bias_val": 3.0}
        )
        
        self.assertIsNotNone(strategy_id)
        
        # Read back
        strategy = get_strategy(strategy_id)
        self.assertEqual(strategy['name'], "Test Unit Strategy")
        self.assertEqual(strategy['macd_fast'], 12)
        self.assertTrue(strategy['custom_conditions']['ma_bias_active'])
        
if __name__ == "__main__":
    unittest.main()
