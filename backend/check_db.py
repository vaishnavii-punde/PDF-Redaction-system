import sqlite3

def explore_db():
    try:
        conn = sqlite3.connect('audit.db')
        cursor = conn.cursor()
        
        # 1. Get List of Tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"📊 Tables found in audit.db: {[t[0] for t in tables]}")
        
        # 2. Get Column Names for each table
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            col_names = [c[1] for c in columns]
            print(f"  └─ Table '{table_name}' has columns: {col_names}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    explore_db()