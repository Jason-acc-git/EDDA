import sqlite3
from app.services.auth_service import get_password_hash

def add_admin_user():
    """
    'admin' 역할을 가진 새로운 사용자를 추가합니다.
    """
    conn = sqlite3.connect('admin.db')
    cur = conn.cursor()

    try:
        name = "admin"
        emp_no = "0000"
        dept = "IT"
        position = "Administrator"
        work_type = "9-6"
        role = "admin"
        email = "admin@example.com"
        password = "admin123"
        hashed_password = get_password_hash(password)

        cur.execute("INSERT INTO employees (name, emp_no, dept, position, work_type, role, email, hashed_password) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                    (name, emp_no, dept, position, work_type, role, email, hashed_password))
        
        conn.commit()
        print(f"- '{name}' 사용자가 추가되었습니다. (비밀번호: {password})")

    except sqlite3.IntegrityError:
        print(f"- '{name}' 사용자는 이미 존재합니다.")
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_admin_user()
