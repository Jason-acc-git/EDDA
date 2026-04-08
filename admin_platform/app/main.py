from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
from sqlalchemy.orm import Session
from sqlalchemy import text

from .api import employee_routes, request_routes, admin_routes
from .db.database import init_db, get_db
from .models.schemas import User
from .services.auth_service import (
    verify_password, create_access_token, get_current_user, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
)

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters['fromjson'] = json.loads
templates.env.filters['to_datetime'] = lambda s: datetime.strptime(s, '%Y-%m-%d') if s else None
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    employees_result = db.execute(text("SELECT name FROM employees")).fetchall()
    employees = [row[0] for row in employees_result]
    message = request.query_params.get('message')
    return templates.TemplateResponse("home.html", {"request": request, "employees": employees, "message": message})

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    employees_result = db.execute(text("SELECT name FROM employees")).fetchall()
    employees = [row[0] for row in employees_result]
    return templates.TemplateResponse("home.html", {"request": request, "employees": employees, "error": None})

@app.post("/login")
def login(request: Request, name: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user_result = db.execute(text("SELECT hashed_password, password_changed_at FROM employees WHERE name = :name"), {"name": name}).fetchone()

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
        return templates.TemplateResponse(
            "home.html",
            {"request": request, "employees": employees, "error": "이름 또는 비밀번호가 올바르지 않습니다."}
        )

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, page: int = 1, db: Session = Depends(get_db), current_user: User = Depends(get_current_user, use_cache=False)):
    per_page = 5
    offset = (page - 1) * per_page

    total_requests_result = db.execute(text("SELECT COUNT(*) FROM requests WHERE name = :name"), {"name": current_user.name}).fetchone()
    total_requests = total_requests_result[0]
    total_pages = (total_requests + per_page - 1) // per_page

    requests_raw = db.execute(text("SELECT * FROM requests WHERE name = :name ORDER BY id DESC LIMIT :limit OFFSET :offset"), {"name": current_user.name, "limit": per_page, "offset": offset}).fetchall()

    requests = []
    for r in requests_raw:
        r_dict = dict(r._mapping)
        try:
            content = json.loads(r_dict['content'])
            summary = ""
            if r_dict['type'] == '시간외 근무':
                hours = content.get('work_hours_weekday', 0) + content.get('work_hours_holiday', 0)
                compensation = content.get('compensation', '')
                summary = f"{hours}시간 - {compensation}"
            elif r_dict['type'] == '출장':
                start = datetime.strptime(content.get('start_date'), '%Y-%m-%d') if content.get('start_date') else None
                end = datetime.strptime(content.get('end_date'), '%Y-%m-%d') if content.get('end_date') else None
                nights = (end - start).days if start and end else 0
                region = content.get('region', '') if content.get('region') else content.get('region_other', '')
                summary = f"{nights}박 - {region}"
            elif r_dict['type'] == '자기개발비':
                summary = f"{content.get('course_title', '')} - {int(content.get('cost', 0)):,}원"
            elif r_dict['type'] in ['대휴 사용', '대휴신청']:
                summary = f"{content.get('leave_date', '')} - {content.get('hours', '')}시간"
            r_dict['summary'] = summary
        except (json.JSONDecodeError, KeyError):
            r_dict['summary'] = r_dict['content']
        requests.append(r_dict)

    current_month = datetime.now().strftime('%Y-%m')
    monthly_overtime_result = db.execute(text("""
        SELECT SUM(CAST(json_extract(content, '$.work_hours_weekday') AS INTEGER) + CAST(json_extract(content, '$.work_hours_holiday') AS INTEGER))
        FROM requests 
        WHERE name = :name AND type IN ('시간외 근무', '시간외근무', '오버타임') AND strftime('%Y-%m', created) = :month AND status = 'approved'
    """), {"name": current_user.name, "month": current_month}).fetchone()
    monthly_overtime = monthly_overtime_result[0] or 0

    total_compensatory_hours_result = db.execute(text("""
        SELECT SUM(CAST(json_extract(content, '$.calculated_compensatory_hours') AS INTEGER)) 
        FROM requests 
        WHERE name = :name AND type = '시간외 근무' AND status = 'approved'
    """), {"name": current_user.name}).fetchone()
    total_compensatory_hours = total_compensatory_hours_result[0] or 0

    used_compensatory_hours_result = db.execute(text("SELECT SUM(CAST(json_extract(content, '$.hours') AS INTEGER)) FROM requests WHERE name = :name AND type IN ('대휴 사용', '대휴신청') AND status = 'approved'"), {"name": current_user.name}).fetchone()
    used_compensatory_hours = used_compensatory_hours_result[0] or 0
    remaining_compensatory_hours = total_compensatory_hours - used_compensatory_hours

    current_year = datetime.now().strftime('%Y')
    used_dev_cost_result = db.execute(text("SELECT SUM(cost) FROM requests WHERE name = :name AND type = '자기개발비' AND strftime('%Y', created) = :year AND status = 'approved'"), {"name": current_user.name, "year": current_year}).fetchone()
    used_dev_cost = used_dev_cost_result[0] or 0
    remaining_dev_cost = 2000000 - used_dev_cost

    pending_approvals = 0
    if current_user.role in ['admin', 'manager', 'lead']:
        if current_user.role == 'admin':
            pending_approvals_result = db.execute(text("SELECT COUNT(*) FROM requests WHERE status LIKE '%승인 대기%'")).fetchone()
        else:
            pending_approvals_result = db.execute(text("SELECT COUNT(*) FROM requests WHERE status LIKE :status"), {"status": f'%{current_user.role} 승인 대기%'}).fetchone()
        pending_approvals = pending_approvals_result[0]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request, 
            "requests": requests, 
            "current_user": current_user,
            "monthly_overtime": monthly_overtime,
            "remaining_compensatory_hours": remaining_compensatory_hours,
            "remaining_dev_cost": remaining_dev_cost,
            "page": page,
            "total_pages": total_pages,
            "pending_approvals": pending_approvals
        }
    )

@app.get("/change-password")
def change_password_form(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("change_password.html", {"request": request})

@app.post("/change-password")
def handle_change_password(request: Request, new_password: str = Form(...), confirm_password: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if new_password != confirm_password:
        return templates.TemplateResponse("change_password.html", {"request": request, "error": "새 비밀번호가 일치하지 않습니다."})

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

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/?message=안전하게+로그아웃되었습니다.", status_code=303)
    response.delete_cookie(key="access_token")
    return response

@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@app.post("/forgot-password")
def handle_forgot_password(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    user_result = db.execute(text("SELECT name FROM employees WHERE email = :email"), {"email": email}).fetchone()

    if not user_result:
        return templates.TemplateResponse("forgot_password.html", {"request": request, "error": "입력하신 이메일로 등록된 사용자가 없습니다."})

    temp_password = "temp1234"
    hashed_password = get_password_hash(temp_password)
    db.execute(text("UPDATE employees SET hashed_password = :hashed_password, password_changed_at = :password_changed_at WHERE email = :email"), {
        "hashed_password": hashed_password, 
        "password_changed_at": None, 
        "email": email
    })
    db.commit()

    return templates.TemplateResponse("forgot_password.html", {"request": request, "message": f"임시 비밀번호는 {temp_password} 입니다. 로그인 후 비밀번호를 변경해주세요."})

app.include_router(employee_routes.router)
app.include_router(request_routes.router)
app.include_router(admin_routes.router)
