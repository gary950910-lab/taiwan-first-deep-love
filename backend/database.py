import sqlite3
import os
import json
from datetime import datetime

# DB file at root directory
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "screener_data.db"))

class DBConnectionWrapper:
    """
    A connection wrapper that implements __enter__ and __exit__ to act as a context manager,
    while delegating all other attribute accesses to the underlying sqlite3.Connection.
    This bridges the gap between different developers' code styles.
    """
    def __init__(self, conn):
        self.conn = conn
    
    def __enter__(self):
        return self.conn
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.conn.close()
        
    def __getattr__(self, name):
        return getattr(self.conn, name)

def get_db_connection():
    """
    Returns a DBConnectionWrapper containing a live sqlite3.Connection.
    Configures journal mode, foreign keys, and Row factory.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return DBConnectionWrapper(conn)

def init_db():
    """
    Initializes all 5 database tables used by both developers.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Stocks table to store the scraped stock list
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            market TEXT NOT NULL, -- 'Listed' or 'OTC'
            industry TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        
        # 2. Screening Sessions
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS screening_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            scope TEXT NOT NULL, -- 'Taiwan50', 'Listed', 'OTC', 'All'
            filters_json TEXT NOT NULL,
            matched_count INTEGER DEFAULT 0
        )
        """)
        
        # 3. Screening Results
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS screening_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            close_price REAL,
            industry TEXT,
            indicators_json TEXT,
            FOREIGN KEY (session_id) REFERENCES screening_sessions(id) ON DELETE CASCADE
        )
        """)
        
        # 4. scan_history
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_date TEXT NOT NULL,
            strategy_name TEXT NOT NULL,
            conditions_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 5. scan_results
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            history_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            price REAL,
            volume INTEGER,
            indicators_json TEXT,
            FOREIGN KEY (history_id) REFERENCES scan_history (id) ON DELETE CASCADE
        )
        """)

def save_scan_record(scan_date, strategy_name, conditions, results):
    """
    儲存一筆掃描紀錄與對應的結果
    :param conditions: dict
    :param results: list of dicts [{'ticker': '2330.TW', 'price': 600, 'volume': 1000, 'indicators': {...}}, ...]
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 寫入 history
        conditions_json = json.dumps(conditions, ensure_ascii=False)
        cursor.execute("""
            INSERT INTO scan_history (scan_date, strategy_name, conditions_json)
            VALUES (?, ?, ?)
        """, (scan_date, strategy_name, conditions_json))
        
        history_id = cursor.lastrowid
        
        # 寫入 results
        for row in results:
            indicators_json = json.dumps(row.get("indicators", {}), ensure_ascii=False)
            cursor.execute("""
                INSERT INTO scan_results (history_id, ticker, price, volume, indicators_json)
                VALUES (?, ?, ?, ?, ?)
            """, (history_id, row["ticker"], row.get("price"), row.get("volume"), indicators_json))
            
        return history_id

def get_all_records():
    """取得所有掃描紀錄列表"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM scan_history ORDER BY created_at DESC
        """)
        records = [dict(row) for row in cursor.fetchall()]
        
        # Parse JSON
        for r in records:
            r["conditions"] = json.loads(r["conditions_json"])
            del r["conditions_json"]
            
        return records

def get_record_detail(history_id):
    """取得特定紀錄明細及選股結果"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 取得 history
        cursor.execute("SELECT * FROM scan_history WHERE id = ?", (history_id,))
        history_row = cursor.fetchone()
        if not history_row:
            return None
            
        history = dict(history_row)
        history["conditions"] = json.loads(history["conditions_json"])
        del history["conditions_json"]
        
        # 取得 results
        cursor.execute("SELECT * FROM scan_results WHERE history_id = ?", (history_id,))
        results = [dict(row) for row in cursor.fetchall()]
        
        for r in results:
            r["indicators"] = json.loads(r["indicators_json"])
            del r["indicators_json"]
            
        history["results"] = results
        return history

def delete_record(history_id):
    """刪除特定紀錄 (透過 ON DELETE CASCADE 連動刪除 results)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scan_history WHERE id = ?", (history_id,))
        return cursor.rowcount > 0

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
