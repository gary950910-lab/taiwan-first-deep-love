import pandas as pd
import subprocess
import os
import re
import io
from datetime import datetime
from backend.database import get_db_connection

def scrape_stocks():
    # URL for listed (上市) stocks
    url_listed = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    # URL for OTC (上櫃) stocks
    url_otc = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"
    
    stocks_to_save = []
    
    for url, market in [(url_listed, 'Listed'), (url_otc, 'OTC')]:
        temp_file = f"temp_{market.lower()}.html"
        try:
            print(f"Scraping {market} stocks from {url} using curl.exe...")
            # Use subprocess to run curl.exe which is less likely to be blocked
            subprocess.run([
                "curl.exe", "-k", "-s",
                "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                url, "-o", temp_file
            ], check=True)
            
            if not os.path.exists(temp_file):
                print(f"Failed to download HTML for {market}")
                continue
                
            # Read HTML file using big5 encoding (TWSE/TPEx standard)
            with open(temp_file, "r", encoding="big5", errors="ignore") as f:
                html_content = f.read()
                
            # Parse HTML tables
            dfs = pd.read_html(io.StringIO(html_content))
            if not dfs:
                print(f"No tables found for {market}")
                continue
                
            df = dfs[0]
            
            # First row is headers
            df.columns = df.iloc[0]
            df = df[1:]
            
            count = 0
            for _, row in df.iterrows():
                val = row.get('有價證券代號及名稱')
                if pd.isna(val) or not isinstance(val, str):
                    continue
                
                # Split code and name (separated by space/full-width space)
                parts = re.split(r'[\s\u3000]+', val.strip())
                if len(parts) >= 2:
                    symbol = parts[0]
                    name = parts[1]
                    
                    # Keep only standard 4-digit stock symbols (exclude ETFs, Warrants, CBs etc.)
                    if re.match(r'^\d{4}$', symbol):
                        industry = row.get('產業別', '')
                        if pd.isna(industry) or not industry:
                            industry = '其他'
                        else:
                            industry = str(industry).strip()
                            
                        stocks_to_save.append({
                            'symbol': symbol,
                            'name': name,
                            'market': market,
                            'industry': industry,
                            'updated_at': datetime.now().isoformat()
                        })
                        count += 1
            print(f"Parsed {count} stocks from {market}")
        except Exception as e:
            print(f"Error scraping {market}: {e}")
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            
    # Save to SQLite Database
    if stocks_to_save:
        conn = get_db_connection()
        cursor = conn.cursor()
        print(f"Saving {len(stocks_to_save)} stocks to database...")
        try:
            # Clean existing entries to start fresh
            cursor.execute("DELETE FROM stocks")
            
            for s in stocks_to_save:
                cursor.execute("""
                INSERT INTO stocks (symbol, name, market, industry, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """, (s['symbol'], s['name'], s['market'], s['industry'], s['updated_at']))
            conn.commit()
            print(f"Successfully updated database with {len(stocks_to_save)} stocks!")
            return len(stocks_to_save)
        except Exception as db_err:
            print(f"Database error while saving stocks: {db_err}")
            conn.rollback()
        finally:
            conn.close()
    return 0

if __name__ == "__main__":
    from backend.database import init_db
    init_db()
    scrape_stocks()
