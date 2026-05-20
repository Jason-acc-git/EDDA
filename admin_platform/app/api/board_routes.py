from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..db.database import get_db
from datetime import datetime

router = APIRouter()

# 로그인 상태 확인을 위한 함수 (optional)
def get_current_user_optional(request: Request):
    """로그인 상태를 확인하되, 로그인하지 않아도 에러를 발생시키지 않음"""
    try:
        access_token = request.cookies.get("access_token")
        if not access_token:
            return None
            
        # JWT 토큰 디코딩 (간단한 방법)
        if "Bearer " in access_token:
            token = access_token.replace("Bearer ", "")
            # 여기서는 간단하게 토큰에 admin이 포함되어 있는지만 확인
            if "admin" in token:
                # 실제로는 JWT 디코딩을 해야 하지만, 임시로 간단한 방법 사용
                class User:
                    def __init__(self, name):
                        self.name = name
                return User("admin")
            else:
                # 다른 사용자의 경우
                class User:
                    def __init__(self, name):
                        self.name = name
                return User("user")
        return None
    except Exception as e:
        print(f"DEBUG: 로그인 확인 중 에러: {e}")
        return None

@router.get("/board", response_class=HTMLResponse)
def board_page(request: Request, db: Session = Depends(get_db), notice_page: int = 1, suggestion_page: int = 1):
    per_page = 5  # 각 카테고리별 5개씩
    
    # 현재 사용자 확인
    current_user = get_current_user_optional(request)
    is_logged_in = current_user is not None
    is_admin = current_user and current_user.name == "admin"
    
    print(f"DEBUG: current_user: {current_user}")
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
    notice_total_pages = (notice_total + per_page - 1) // per_page
    
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
    suggestion_total_pages = (suggestion_total + per_page - 1) // per_page
    
    print(f"DEBUG: 템플릿에 전달되는 값 - is_logged_in: {is_logged_in}, is_admin: {is_admin}")
    
    from ..main import templates
    return templates.TemplateResponse(
        "board.html",
        {
            "request": request,
            "notices": notices,
            "suggestions": suggestions,
            "notice_page": notice_page,
            "notice_total_pages": notice_total_pages,
            "suggestion_page": suggestion_page,
            "suggestion_total_pages": suggestion_total_pages,
            "is_admin": is_admin,
            "is_logged_in": is_logged_in
        }
    )

@router.post("/board/create_suggestion")
def create_suggestion(
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    # 건의사항 글 작성 (작성자는 "익명"으로 고정)
    db.execute(text("""
        INSERT INTO board_posts (category, title, content, author, created_at, updated_at)
        VALUES ('건의사항', :title, :content, '익명', :created_at, :updated_at)
    """), {
        "title": title,
        "content": content,
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    db.commit()
    
    return RedirectResponse(url="/board", status_code=303)

@router.post("/board/create_notice")
def create_notice(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    # admin 권한 확인
    current_user = get_current_user_optional(request)
    if not current_user or current_user.name != "admin":
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
    
    # 전체 게시글 수
    total_count = db.execute(text("""
        SELECT COUNT(*) FROM board_posts WHERE category = :category
    """), {"category": category}).scalar()
    
    # 게시글 가져오기
    posts = db.execute(text("""
        SELECT id, title, author, created_at 
        FROM board_posts 
        WHERE category = :category 
        ORDER BY created_at DESC 
        LIMIT :limit OFFSET :offset
    """), {"category": category, "limit": per_page, "offset": offset}).fetchall()
    
    # 페이지 정보 계산
    total_pages = (total_count + per_page - 1) // per_page
    
    from ..main import templates
    return templates.TemplateResponse(
        "board_category.html",
        {
            "request": request,
            "category": category,
            "posts": posts,
            "current_page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }
    )

@router.get("/board/post/{post_id}", response_class=HTMLResponse)
def board_post_detail(request: Request, post_id: int, db: Session = Depends(get_db)):
    # 게시글 상세 정보
    post = db.execute(text("""
        SELECT id, category, title, content, author, created_at 
        FROM board_posts 
        WHERE id = :post_id
    """), {"post_id": post_id}).fetchone()
    
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    
    from ..main import templates
    return templates.TemplateResponse(
        "board_post.html",
        {
            "request": request,
            "post": post
        }
    )
