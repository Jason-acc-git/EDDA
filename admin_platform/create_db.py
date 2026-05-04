import sqlite3
import os

DB_NAME = "admin.db"

def get_conn():
    return sqlite3.connect(DB_NAME)

def init_db():
    print(f"Creating database at {os.path.abspath(DB_NAME)}")
    conn = get_conn()
    cur = conn.cursor()

    # 직원 정보
    cur.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT,
        content TEXT,
        status TEXT,
        created TEXT,
        approver TEXT,
        approved_by_lead TEXT,
        approved_by_manager TEXT,
        reject_reason TEXT,
        cost INTEGER,
        approved_by_lead_at TEXT,
        approved_by_manager_at TEXT,
        file_path TEXT
    )
    """)

    # 신청서
    cur.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        emp_no TEXT,
        dept TEXT,
        position TEXT,
        work_type TEXT,
        role TEXT,
        email TEXT,
        signature TEXT,
        hashed_password TEXT,
        password_changed_at TEXT
    )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully")

if __name__ == "__main__":
    init_db()
