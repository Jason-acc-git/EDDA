import sqlite3
from app.services.auth_service import get_password_hash

def reset_all_passwords():
    conn = sqlite3.connect('admin.db')
    cur = conn.cursor()

    try:
        new_password = "12345"
        hashed_password = get_password_hash(new_password)

        cur.execute("UPDATE employees SET hashed_password = ?, password_changed_at = NULL", (hashed_password,))
        
        conn.commit()
        print(f"모든 직원의 비밀번호가 '{new_password}'로 재설정되었습니다.")

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    reset_all_passwords()
