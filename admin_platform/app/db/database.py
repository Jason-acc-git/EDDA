from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

import sqlite3

DB_NAME = "admin.db"

def get_conn():
    return sqlite3.connect(DB_NAME)


def init_db():

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
        approved_by_manager_at TEXT

    )
    """)

    try:
        cur.execute("ALTER TABLE requests ADD COLUMN cost INTEGER")
        cur.execute("ALTER TABLE requests ADD COLUMN approved_by_lead_at TEXT")
        cur.execute("ALTER TABLE requests ADD COLUMN approved_by_manager_at TEXT")
        cur.execute("ALTER TABLE requests ADD COLUMN file_path TEXT")
    except:
        pass


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

def get_user_role(name):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""

        SELECT role
        FROM employees
        WHERE name = ?

    """, (name,))

    row = cur.fetchone()

    conn.close()

    if row:
        return row[0]

    return None

def get_approver_by_role(role):

    if role == "employee":
        return "lead"

    if role == "lead":
        return "manager"

    if role == "manager":
        return "admin"

    return None

def get_approver_email(approver_role):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT email
        FROM employees
        WHERE role = ?
    """, (approver_role,))

    row = cur.fetchone()

    conn.close()

    if row:
        return row[0]

    return None
