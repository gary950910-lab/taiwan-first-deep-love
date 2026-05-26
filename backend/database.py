import sqlite3
import json
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'screener_data.db')

def init_db():
    """Initialize the SQLite database with required tables."""
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 建立歷史掃描紀錄表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                conditions_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 建立掃描結果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                history_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                price REAL,
                volume INTEGER,
                indicators_json TEXT,
                FOREIGN KEY (history_id) REFERENCES scan_history (id) ON DELETE CASCADE
            )
        ''')
        conn.commit()

@contextmanager
def get_db_connection():
    """Context manager for SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 開啟外鍵約束 (ON DELETE CASCADE)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()

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
        cursor.execute('''
            INSERT INTO scan_history (scan_date, strategy_name, conditions_json)
            VALUES (?, ?, ?)
        ''', (scan_date, strategy_name, conditions_json))
        
        history_id = cursor.lastrowid
        
        # 寫入 results
        for row in results:
            indicators_json = json.dumps(row.get('indicators', {}), ensure_ascii=False)
            cursor.execute('''
                INSERT INTO scan_results (history_id, ticker, price, volume, indicators_json)
                VALUES (?, ?, ?, ?, ?)
            ''', (history_id, row['ticker'], row.get('price'), row.get('volume'), indicators_json))
            
        conn.commit()
        return history_id

def get_all_records():
    """取得所有掃描紀錄列表"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM scan_history ORDER BY created_at DESC
        ''')
        records = [dict(row) for row in cursor.fetchall()]
        
        # Parse JSON
        for r in records:
            r['conditions'] = json.loads(r['conditions_json'])
            del r['conditions_json']
            
        return records

def get_record_detail(history_id):
    """取得特定紀錄明細及選股結果"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 取得 history
        cursor.execute('SELECT * FROM scan_history WHERE id = ?', (history_id,))
        history_row = cursor.fetchone()
        if not history_row:
            return None
            
        history = dict(history_row)
        history['conditions'] = json.loads(history['conditions_json'])
        del history['conditions_json']
        
        # 取得 results
        cursor.execute('SELECT * FROM scan_results WHERE history_id = ?', (history_id,))
        results = [dict(row) for row in cursor.fetchall()]
        
        for r in results:
            r['indicators'] = json.loads(r['indicators_json'])
            del r['indicators_json']
            
        history['results'] = results
        return history

def delete_record(history_id):
    """刪除特定紀錄 (透過 ON DELETE CASCADE 連動刪除 results)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM scan_history WHERE id = ?', (history_id,))
        conn.commit()
        return cursor.rowcount > 0
