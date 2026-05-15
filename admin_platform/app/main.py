from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import json
from sqlalchemy.orm import Session
from sqlalchemy import text
import os

def get_pending_approvals_count():
    """승인 대기 건수를 데이터베이스에서 가져오는 함수"""
    try:
        import sqlite3
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM requests WHERE status LIKE '%대기' OR status = '재신청'")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"승인 대기 건수 조회 오류: {e}")
        return 0

from jinja2 import Environment, FileSystemLoader

from .api import employee_routes, request_routes, admin_routes
from .db.database import init_db, get_db
from .models.schemas import User
from .services.auth_service import (
    verify_password, create_access_token, get_current_user, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
)

app = FastAPI()

# 템플릿 설정
template_dir = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    cache_size=0,
    auto_reload=True
)
jinja_env.filters['fromjson'] = json.loads
jinja_env.filters['to_datetime'] = lambda s: datetime.strptime(s, '%Y-%m-%d') if s else None

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event("startup")
def startup():
    init_db()

def render_template(template_name: str, context: dict):
    template = jinja_env.get_template(template_name)
    html_content = template.render(context)
    return HTMLResponse(content=html_content)

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    employees_result = db.execute(text("SELECT name FROM employees")).fetchall()
    employees = [row[0] for row in employees_result]
    message = request.query_params.get('message')
    return render_template("home.html", {"request": request, "employees": employees, "message": message})

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    employees_result = db.execute(text("SELECT name FROM employees")).fetchall()
    employees = [row[0] for row in employees_result]
    return render_template("home.html", {"request": request, "employees": employees, "error": None})

@app.post("/login")
def login(request: Request, name: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user_result = db.execute(text("SELECT hashed_password, password_changed_at FROM employees WHERE name = :name"), {"name": name}).fetchone()

    # 비밀번호 길이 제한 (bcrypt는 72바이트까지만 지원)
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')

    if user_result and verify_password(password, user_result[0]):
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": name}, expires_delta=access_token_expires)
        
        password_changed_at = user_result[1]
        if password_changed_at is None:
            response = RedirectResponse(url="/change-password", status_code=303)
        else:
            response = RedirectResponse(url="/dashboard", status_code=303)
        
        response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
        return response
    else:
        employees_result = db.execute(text("SELECT name FROM employees")).fetchall()
        employees = [row[0] for row in employees_result]
        return render_template("home.html", {"request": request, "employees": employees, "error": "이름 또는 비밀번호가 올바르지 않습니다."})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, page: int = 1, db: Session = Depends(get_db), current_user: User = Depends(get_current_user, use_cache=False)):
    return render_template("dashboard.html", {
        "request": request, 
        "requests": get_user_requests(current_user.name, page), 
        "current_user": current_user,
        "monthly_overtime": get_monthly_overtime_hours(current_user.name),
        "remaining_compensatory_hours": get_remaining_compensatory_hours(current_user.name),
        "remaining_dev_cost": get_remaining_dev_cost(current_user.name),
        "page": page,
        "total_pages": (get_user_requests_count(current_user.name) + 9) // 10,
        "pending_approvals": get_pending_approvals_count()
    })

@app.get("/test")
def test():
    return {"message": "Server is working"}

app.include_router(employee_routes.router)
app.include_router(request_routes.router)
app.include_router(admin_routes.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

# 다른 라우터들이 사용할 수 있도록 전역 templates 객체 생성
class GlobalTemplates:
    @staticmethod
    def TemplateResponse(template_name: str, context: dict):
        template = jinja_env.get_template(template_name)
        html_content = template.render(context)
        return HTMLResponse(content=html_content)

# 전역 templates 객체 생성 (다른 파일들이 import해서 사용)
templates = GlobalTemplates()

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/?message=안전하게+로그아웃되었습니다.", status_code=303)
    response.delete_cookie(key="access_token")
    return response

@app.get("/change-password")
def change_password_form(request: Request, current_user: User = Depends(get_current_user)):
    return render_template("change_password.html", {"request": request})

@app.post("/change-password")
def handle_change_password(request: Request, new_password: str = Form(...), confirm_password: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if new_password != confirm_password:
        return render_template("change_password.html", {"request": request, "error": "새 비밀번호가 일치하지 않습니다."})

    # 비밀번호 길이 제한
    if len(new_password.encode('utf-8')) > 72:
        new_password = new_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')

    hashed_password = get_password_hash(new_password)
    db.execute(text("UPDATE employees SET hashed_password = :hashed_password, password_changed_at = :password_changed_at WHERE name = :name"), {
        "hashed_password": hashed_password, 
        "password_changed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
        "name": current_user.name
    })
    db.commit()

    response = RedirectResponse(url="/?message=비밀번호가+성공적으로+변경되었습니다.+다시+로그인해주세요.", status_code=303)
    response.delete_cookie(key="access_token")
    return response

@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    return render_template("forgot_password.html", {"request": request})

@app.post("/forgot-password")
def handle_forgot_password(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    user_result = db.execute(text("SELECT name FROM employees WHERE email = :email"), {"email": email}).fetchone()

    if not user_result:
        return render_template("forgot_password.html", {"request": request, "error": "입력하신 이메일로 등록된 사용자가 없습니다."})

    temp_password = "temp1234"
    # 비밀번호 길이 제한
    if len(temp_password.encode('utf-8')) > 72:
        temp_password = temp_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    
    hashed_password = get_password_hash(temp_password)
    db.execute(text("UPDATE employees SET hashed_password = :hashed_password, password_changed_at = :password_changed_at WHERE email = :email"), {
        "hashed_password": hashed_password, 
        "password_changed_at": None, 
        "email": email
    })
    db.commit()

    return render_template("forgot_password.html", {"request": request, "message": f"임시 비밀번호는 {temp_password} 입니다. 로그인 후 비밀번호를 변경해주세요."})

@app.post("/change-password")
def handle_change_password(request: Request, new_password: str = Form(...), confirm_password: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if new_password != confirm_password:
        return render_template("change_password.html", {"request": request, "error": "새 비밀번호가 일치하지 않습니다."})

    # 비밀번호 길이 제한
    if len(new_password.encode('utf-8')) > 72:
        new_password = new_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')

    hashed_password = get_password_hash(new_password)
    db.execute(text("UPDATE employees SET hashed_password = :hashed_password, password_changed_at = :password_changed_at WHERE name = :name"), {
        "hashed_password": hashed_password, 
        "password_changed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
        "name": current_user.name
    })
    db.commit()

    response = RedirectResponse(url="/?message=비밀번호가+성공적으로+변경되었습니다.+다시+로그인해주세요.", status_code=303)
    response.delete_cookie(key="access_token")
    return response

@app.get("/favicon.ico")
def favicon():
    return RedirectResponse(url="/static/images/favicon-32x32.png")

@app.get("/apple-touch-icon.png")
def apple_touch_icon():
    return RedirectResponse(url="/static/images/apple-touch-icon.png")

@app.get("/apple-touch-icon-precomposed.png")
def apple_touch_icon_precomposed():
    return RedirectResponse(url="/static/images/apple-touch-icon-precomposed.png")

@app.get("/favicon.ico")
def favicon():
    return RedirectResponse(url="/static/images/favicon-32x32.png")

@app.get("/apple-touch-icon.png")
def apple_touch_icon():
    return RedirectResponse(url="/static/images/apple-touch-icon.png")

@app.get("/test/pending-count")
def test_pending_count():
    try:
        import sqlite3
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM requests WHERE status = 'approver 승인 대기'")
        count = cursor.fetchone()[0]
        conn.close()
        return {"pending_count": count, "status": "success"}
    except Exception as e:
        return {"error": str(e), "status": "error"}

@app.get("/test/user-requests/{user_name}")
def test_user_requests(user_name: str):
    try:
        import sqlite3
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, type, content, status
            FROM requests
            WHERE name = ?
            ORDER BY id DESC
        """, (user_name,))
        requests = cursor.fetchall()
        conn.close()
        return {"user_name": user_name, "requests": requests, "count": len(requests)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/test/all-requests")
def test_all_requests():
    try:
        import sqlite3
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, type, content, status FROM requests ORDER BY id DESC")
        requests = cursor.fetchall()
        conn.close()
        return {"requests": requests, "count": len(requests)}
    except Exception as e:
        return {"error": str(e)}




def get_monthly_overtime_hours(user_name: str):
    """이번 달 누적 시간외근무 시간 계산"""
    try:
        import sqlite3
        import json
        from datetime import datetime
        
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        
        # 이번 달 시작일과 종료일
        today = datetime.now()
        start_of_month = today.replace(day=1).strftime('%Y-%m-%d')
        if today.month == 12:
            end_of_month = today.replace(year=today.year+1, month=1, day=1).strftime('%Y-%m-%d')
        else:
            end_of_month = today.replace(month=today.month+1, day=1).strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT content FROM requests 
            WHERE name = ? AND type = '시간외 근무' AND status = 'approved'
            AND created BETWEEN ? AND ?
        """, (user_name, start_of_month, end_of_month))
        
        total_hours = 0
        for req in cursor.fetchall():
            if req[0]:
                content = json.loads(req[0])
                total_hours += content.get('work_hours_weekday', 0) + content.get('work_hours_holiday', 0)
        
        conn.close()
        return total_hours
    except Exception as e:
        print(f"월간 시간외근무 계산 오류: {e}")
        return 0

def get_remaining_compensatory_hours(user_name: str):
    """남은 대휴 시간 계산"""
    try:
        import sqlite3
        import json
        
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        
        # 승인된 시간외근무에서 대휴 시간 계산
        cursor.execute("""
            SELECT content FROM requests 
            WHERE name = ? AND type = '시간외 근무' AND status = 'approved'
        """, (user_name,))
        
        total_overtime_hours = 0
        for req in cursor.fetchall():
            if req[0]:
                content = json.loads(req[0])
                total_overtime_hours += content.get('calculated_compensatory_hours', 0)
        
        # 사용한 대휴 시간 계산
        cursor.execute("""
            SELECT content FROM requests 
            WHERE name = ? AND type = '대휴신청' AND status = 'approved'
        """, (user_name,))
        
        used_leave_hours = 0
        for req in cursor.fetchall():
            if req[0]:
                content = json.loads(req[0])
                used_leave_hours += content.get('hours', 0)
        
        conn.close()
        return total_overtime_hours - used_leave_hours
    except Exception as e:
        print(f"대휴 시간 계산 오류: {e}")
        return 0

def get_remaining_dev_cost(user_name: str):
    """자기개발비 잔액 계산"""
    try:
        import sqlite3
        import json
        
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT content FROM requests 
            WHERE name = ? AND type = '자기개발비' AND status = 'approved'
        """, (user_name,))
        
        used_dev_cost = 0
        for req in cursor.fetchall():
            if req[0]:
                content = json.loads(req[0])
                used_dev_cost += int(content.get('cost', '0'))
        
        conn.close()
        return 2000000 - used_dev_cost
    except Exception as e:
        print(f"자기개발비 계산 오류: {e}")
        return 2000000
def get_user_requests_count(user_name: str):
    """사용자의 총 신청내역 개수를 가져오는 함수"""
    try:
        import sqlite3
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM requests WHERE name = ?", (user_name,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"사용자 신청내역 개수 조회 오류: {e}")
        return 0

def get_user_requests(user_name: str, page: int = 1, per_page: int = 10):
    """현재 사용자의 신청내역을 안전하게 가져오는 함수"""
    try:
        import sqlite3
        import json
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, type, content, status, created, reject_reason
            FROM requests
            WHERE name = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (user_name, per_page, (page - 1) * per_page))
        raw_requests = cursor.fetchall()
        conn.close()

        # 안전한 데이터 변환
        formatted_requests = []
        for req in raw_requests:
            # 실제 content 파싱 및 안전한 처리
            try:
                if req[2]:
                    content = json.loads(req[2])
                else:
                    content = {}
            except:
                content = {}
            
            # 필수 필드들 안전하게 설정
            safe_content = {
                "start_date": content.get("start_date") or "2024-01-01",
                "end_date": content.get("end_date") or "2024-01-01", 
                "work_date": content.get("work_date") or "2024-01-01",
                "leave_date": content.get("leave_date") or "2024-01-01"
            }
            

            # 신청 유형별 구체적인 summary 생성
            summary = ""
            if req[1] == "시간외 근무":
                weekday_hours = content.get("work_hours_weekday", 0)
                holiday_hours = content.get("work_hours_holiday", 0)
                compensation = content.get("compensation", "")
                total_hours = weekday_hours + holiday_hours
                if compensation == "대체휴가":
                    summary = f"{total_hours}시간-대체휴가"
                else:
                    summary = f"{total_hours}시간-수당지급"
            elif req[1] == "대휴 사용" or req[1] == "대휴신청":
                hours = content.get("hours", 0)
                summary = f"{hours}시간 대휴사용"
            elif req[1] == "출장":
                region = content.get("region", content.get("region_other", ""))
                summary = f"{region} 출장"
            elif req[1] == "자기개발비":
                cost = content.get("cost", 0)
                course_title = content.get("course_title", "")
                summary = f"{course_title} - {int(cost):,}원"
            else:
                summary = f"{req[1]} 신청"

            formatted_req = {
                'id': req[0],
                'type': req[1],
                'content': json.dumps(safe_content),
                'status': req[3],
                'created': req[4] if req[4] else '2024-01-01 00:00:00',
                'summary': summary,
                'reject_reason': req[5] if len(req) > 5 and req[5] else ''
            }
            formatted_requests.append(formatted_req)

        return formatted_requests
    except Exception as e:
        print(f"사용자 신청내역 조회 오류: {e}")
        return []
