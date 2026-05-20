from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import os

from ..db.database import get_db
from ..services.auth_service import get_current_user, get_token_from_cookie
from ..models.schemas import User

router = APIRouter()

def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    """로그인 상태를 확인하되, 로그인하지 않아도 에러를 발생시키지 않음"""
    try:
        # auth_service의 검증된 함수들 사용
        # 모든 쿠키 출력
        print(f"DEBUG: 모든 쿠키: {dict(request.cookies)}")
        # 모든 쿠키 출력
        print(f"DEBUG: 모든 쿠키: {dict(request.cookies)}")
        token = get_token_from_cookie(request)
        print(f"DEBUG: token = {token}")
        
        if not token:
            print("DEBUG: token이 없음")
            return None
            
        # get_current_user 함수 사용 (예외 처리로 감싸기)
        try:
            user = get_current_user(request, db, use_cache=False)
            print(f"DEBUG: 인증 성공 - user: {user.name}")
            return user
        except HTTPException:
            print("DEBUG: JWT 토큰 검증 실패")
            return None
            
    except Exception as e:
        print(f"DEBUG: 인증 중 예외 발생: {e}")
        return None

@router.get("/board", response_class=HTMLResponse)
def board_main(request: Request, db: Session = Depends(get_db), notice_page: int = 1, suggestion_page: int = 1):
    per_page = 5
    
    # 현재 사용자 확인 (로그인하지 않아도 접근 가능)
    current_user = get_current_user_optional(request, db)
    is_logged_in = current_user is not None
    is_admin = current_user and current_user.role == "Admin"

    print(f"DEBUG: current_user: {current_user}")
    if current_user:
        print(f"DEBUG: current_user.name: '{current_user.name}'")
    print(f"DEBUG: is_logged_in: {is_logged_in}, is_admin: {is_admin}")

    # 공지사항 페이지네이션 (내용도 함께 가져오기)
    notice_offset = (notice_page - 1) * per_page
    notices = db.execute(text("""
        SELECT id, title, content, author, created_at
        FROM board_posts
        WHERE category = '공지사항'
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """), {"limit": per_page, "offset": notice_offset}).fetchall()

    notice_total = db.execute(text("""
        SELECT COUNT(*) FROM board_posts WHERE category = '공지사항'
    """)).scalar()

    # 건의사항 페이지네이션 (내용도 함께 가져오기)
    suggestion_offset = (suggestion_page - 1) * per_page
    suggestions = db.execute(text("""
        SELECT id, title, content, author, created_at
        FROM board_posts
        WHERE category = '건의사항'
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """), {"limit": per_page, "offset": suggestion_offset}).fetchall()

    suggestion_total = db.execute(text("""
        SELECT COUNT(*) FROM board_posts WHERE category = '건의사항'
    """)).scalar()

    print(f"DEBUG: 템플릿에 전달되는 값 - is_logged_in: {is_logged_in}, is_admin: {is_admin}")

    from jinja2 import Environment, FileSystemLoader
    template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
    jinja_env = Environment(loader=FileSystemLoader(template_dir), cache_size=0, auto_reload=True)
    template = jinja_env.get_template("board.html")
    
    return HTMLResponse(content=template.render(
        request=request,
        notices=notices,
        suggestions=suggestions,
        notice_page=notice_page,
        suggestion_page=suggestion_page,
        notice_total_pages=(notice_total + per_page - 1) // per_page,
        suggestion_total_pages=(suggestion_total + per_page - 1) // per_page,
        is_logged_in=is_logged_in,
        is_admin=is_admin
    ))

@router.post("/board/create_notice")
def create_notice(request: Request, title: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    # 관리자 권한 확인
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="관리자만 공지사항을 작성할 수 있습니다.")

    # 공지사항 글 작성
    db.execute(text("""
        INSERT INTO board_posts (category, title, content, author, created_at, updated_at)
        VALUES ('공지사항', :title, :content, 'admin', :created_at, :updated_at)
    """), {
        "title": title,
        "content": content,
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    db.commit()

    return RedirectResponse(url="/board", status_code=303)

@router.get("/board/{category}", response_class=HTMLResponse)
def board_category(request: Request, category: str, db: Session = Depends(get_db), page: int = 1):
    # 페이지네이션
    per_page = 10
    offset = (page - 1) * per_page
    
    posts = db.execute(text("""
        SELECT id, title, content, author, created_at
        FROM board_posts
        WHERE category = :category
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """), {"category": category, "limit": per_page, "offset": offset}).fetchall()

    total_posts = db.execute(text("""
        SELECT COUNT(*) FROM board_posts WHERE category = :category
    """), {"category": category}).scalar()

    total_pages = (total_posts + per_page - 1) // per_page

    from jinja2 import Environment, FileSystemLoader
    template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
    jinja_env = Environment(loader=FileSystemLoader(template_dir), cache_size=0, auto_reload=True)
    template = jinja_env.get_template("board_category.html")
    
    return HTMLResponse(content=template.render(
        request=request,
        posts=posts,
        category=category,
        page=page,
        total_pages=total_pages
    ))

@router.post("/board/create_suggestion")
def create_suggestion(request: Request, title: str = Form(...), content: str = Form(...), author: str = Form("익명"), db: Session = Depends(get_db)):
    # 건의사항은 누구나 작성 가능
    db.execute(text("""
        INSERT INTO board_posts (category, title, content, author, created_at, updated_at)
    VALUES ('건의사항', :title, :content, :author, :created_at, :updated_at)
    """), {
        "title": title,
        "content": content,
        "author": author,
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    db.commit()

    return RedirectResponse(url="/board", status_code=303)
