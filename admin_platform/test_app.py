from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

# 절대 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "app", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "app", "static")

print(f"Base directory: {BASE_DIR}")
print(f"Template directory: {TEMPLATE_DIR}")
print(f"Static directory: {STATIC_DIR}")

app = FastAPI()

# 정적 파일 설정
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 템플릿 설정
templates = Jinja2Templates(directory=TEMPLATE_DIR)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("test.html", {"request": request})

@app.get("/test", response_class=HTMLResponse)
def test(request: Request):
    return templates.TemplateResponse("test.html", {"request": request})
