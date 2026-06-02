import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "taiwan_stock.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high performance
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Stocks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            ticker TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            market TEXT NOT NULL,
            industry TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    # 2. Stock prices table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_prices (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            PRIMARY KEY (ticker, date)
        )
    """)
    
    # 3. Strategies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            macd_fast INTEGER DEFAULT 12,
            macd_slow INTEGER DEFAULT 26,
            macd_signal INTEGER DEFAULT 9,
            kd_k INTEGER DEFAULT 9,
            kd_d INTEGER DEFAULT 3,
            bb_length INTEGER DEFAULT 20,
            bb_std REAL DEFAULT 2.0,
            custom_conditions TEXT NOT NULL, -- JSON string
            created_at TEXT NOT NULL
        )
    """)
    
    # 4. Screener history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screener_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            run_date TEXT NOT NULL,
            results TEXT NOT NULL, -- JSON string list of tickers
            created_at TEXT NOT NULL,
            FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_prices_date ON stock_prices (date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_prices_ticker ON stock_prices (ticker)")
    
    conn.commit()
    conn.close()

# --- STOCKS CRUD ---
def insert_stocks(stocks):
    """
    stocks: list of dicts with keys: ticker, code, name, market, industry
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO stocks (ticker, code, name, market, industry, is_active)
        VALUES (:ticker, :code, :name, :market, :industry, 1)
        ON CONFLICT(ticker) DO UPDATE SET
            name=excluded.name,
            market=excluded.market,
            industry=excluded.industry
    """, stocks)
    conn.commit()
    conn.close()

def get_stocks(market=None, industry=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT ticker, code, name, market, industry FROM stocks WHERE is_active = 1"
    params = []
    
    if market:
        query += " AND market = ?"
        params.append(market)
    if industry:
        query += " AND industry = ?"
        params.append(industry)
        
    query += " ORDER BY code ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_unique_industries():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT industry FROM stocks WHERE industry != '' ORDER BY industry ASC")
    rows = cursor.fetchall()
    conn.close()
    return [row['industry'] for row in rows]

# --- STOCK PRICES CRUD ---
def insert_stock_prices(prices):
    """
    prices: list of dicts with keys: ticker, date, open, high, low, close, volume
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO stock_prices (ticker, date, open, high, low, close, volume)
        VALUES (:ticker, :date, :open, :high, :low, :close, :volume)
        ON CONFLICT(ticker, date) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume
    """, prices)
    conn.commit()
    conn.close()

def get_price_history(ticker, start_date=None, end_date=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT date, open, high, low, close, volume FROM stock_prices WHERE ticker = ?"
    params = [ticker]
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
        
    query += " ORDER BY date ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_latest_price_date():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(date) as max_date FROM stock_prices")
    row = cursor.fetchone()
    conn.close()
    return row['max_date'] if row else None

# --- STRATEGIES CRUD ---
def save_strategy(name, macd_fast, macd_slow, macd_signal, kd_k, kd_d, bb_length, bb_std, custom_conditions):
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO strategies (name, macd_fast, macd_slow, macd_signal, kd_k, kd_d, bb_length, bb_std, custom_conditions, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, macd_fast, macd_slow, macd_signal, kd_k, kd_d, bb_length, bb_std, json.dumps(custom_conditions), created_at))
    conn.commit()
    strategy_id = cursor.lastrowid
    conn.close()
    return strategy_id

def get_strategy(strategy_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        res = dict(row)
        res['custom_conditions'] = json.loads(res['custom_conditions'])
        return res
    return None

def get_all_strategies():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategies ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    strategies = []
    for row in rows:
        res = dict(row)
        res['custom_conditions'] = json.loads(res['custom_conditions'])
        strategies.append(res)
    return strategies

def delete_strategy(strategy_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
    conn.commit()
    conn.close()

# --- SCREENER HISTORY CRUD ---
def save_screener_history(strategy_id, run_date, results):
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO screener_history (strategy_id, run_date, results, created_at)
        VALUES (?, ?, ?, ?)
    """, (strategy_id, run_date, json.dumps(results), created_at))
    conn.commit()
    history_id = cursor.lastrowid
    conn.close()
    return history_id

def get_screener_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.id, h.strategy_id, h.run_date, h.results, h.created_at, s.name as strategy_name
        FROM screener_history h
        JOIN strategies s ON h.strategy_id = s.id
        ORDER BY h.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        res = dict(row)
        res['results'] = json.loads(res['results'])
        history.append(res)
    return history

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
