import sys
import os

# 현재 경로 출력
print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path}")

# 경로 추가
sys.path.append('/Users/engineers/EDDA/admin_platform')

try:
    from app.db.database import init_db
    print("Successfully imported init_db")
    init_db()
    print("Database initialized successfully")
except Exception as e:
    print(f"Error: {e}")
