import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "taiwan_stock.db"))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Make sure backend folder exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_db_connection()
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
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
