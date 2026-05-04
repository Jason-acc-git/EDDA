from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import json
from sqlalchemy.orm import Session
from sqlalchemy import text
import os
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
        "requests": [], 
        "current_user": current_user,
        "monthly_overtime": 0,
        "remaining_compensatory_hours": 0,
        "remaining_dev_cost": 2000000,
        "page": 1,
        "total_pages": 1,
        "pending_approvals": 0
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
