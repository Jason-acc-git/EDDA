# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import os
import sqlite3
import json
from datetime import datetime

app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "templates"),
            static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static"))

app.secret_key = "a_very_secret_key"

# Jinja2 필터 추가
@app.template_filter('fromjson')
def fromjson_filter(value):
    if value:
        try:
            return json.loads(value)
        except:
            return {}
    return {}

# 날짜 변환 필터 추가
@app.template_filter('to_datetime')
def to_datetime_filter(value):
    if value:
        try:
            return datetime.strptime(value, '%Y-%m-%d')
        except:
            return None
    return None

def get_db_connection():
    conn = sqlite3.connect('admin.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    message = request.args.get('message')
    try:
        conn = get_db_connection()
        employees_result = conn.execute('SELECT name FROM employees').fetchall()
        conn.close()
        employees = [row['name'] for row in employees_result]
    except Exception as e:
        print(f"Database error: {e}")
        employees = []
    
    # 키워드 인자로 변수 전달
    return render_template("home.html", request=request, employees=employees, message=message)

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory(app.static_folder, path)

@app.route('/login', methods=['POST'])
def login():
    name = request.form.get('name')
    password = request.form.get('password')
    
    try:
        conn = get_db_connection()
        user_result = conn.execute('SELECT hashed_password, password_changed_at, role FROM employees WHERE name = ?', (name,)).fetchone()
        conn.close()
        
        if user_result:
            # 실제로는 비밀번호 검증이 필요하지만, 여기서는 간단히 처리
            session['user'] = name
            session['role'] = user_result['role'] if user_result['role'] else 'employee'
            return redirect('/dashboard')
        else:
            return redirect('/?message=이름+또는+비밀번호가+올바르지+않습니다.')
    except Exception as e:
        print(f"Login error: {e}")
        return redirect('/?message=로그인+중+오류가+발생했습니다.')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    
    try:
        conn = get_db_connection()
        
        # 현재 월 계산
        current_month = datetime.now().strftime('%Y-%m')
        
        # 월간 초과 근무 시간 계산
        monthly_overtime_result = conn.execute("""
            SELECT SUM(CAST(json_extract(content, '$.work_hours_weekday') AS INTEGER) + CAST(json_extract(content, '$.work_hours_holiday') AS INTEGER))
            FROM requests 
            WHERE name = ? AND type IN ('시간외 근무', '시간외근무', '오버타임') AND strftime('%Y-%m', created) = ? AND status = 'approved'
        """, (session['user'], current_month)).fetchone()
        monthly_overtime = monthly_overtime_result[0] or 0
        
        # 총 보상 휴가 시간 계산
        total_compensatory_hours_result = conn.execute("""
            SELECT SUM(CAST(json_extract(content, '$.calculated_compensatory_hours') AS INTEGER)) 
            FROM requests 
            WHERE name = ? AND type = '시간외 근무' AND status = 'approved'
        """, (session['user'],)).fetchone()
        total_compensatory_hours = total_compensatory_hours_result[0] or 0
        
        # 사용한 보상 휴가 시간 계산
        used_compensatory_hours_result = conn.execute("""
            SELECT SUM(CAST(json_extract(content, '$.hours') AS INTEGER)) 
            FROM requests 
            WHERE name = ? AND type IN ('대휴 사용', '대휴신청') AND status = 'approved'
        """, (session['user'],)).fetchone()
        used_compensatory_hours = used_compensatory_hours_result[0] or 0
        remaining_compensatory_hours = total_compensatory_hours - used_compensatory_hours
        
        # 요청 목록 가져오기
        requests_raw = conn.execute("""
            SELECT * FROM requests 
            WHERE name = ? 
            ORDER BY id DESC 
            LIMIT 5
        """, (session['user'],)).fetchall()
        
        conn.close()
        
        # 요청 목록 처리
        requests = []
        for r in requests_raw:
            r_dict = dict(r)
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
        
        # 승인 대기 중인 요청 수 계산
        pending_approvals = 0
        if session.get('role') in ['admin', 'manager', 'lead']:
            conn = get_db_connection()
            if session['role'] == 'admin':
                pending_approvals_result = conn.execute("SELECT COUNT(*) FROM requests WHERE status LIKE '%승인 대기%'").fetchone()
            else:
                pending_approvals_result = conn.execute("SELECT COUNT(*) FROM requests WHERE status LIKE ?", (f'%{session["role"]} 승인 대기%',)).fetchone()
            pending_approvals = pending_approvals_result[0]
            conn.close()
        
        # 키워드 인자로 변수 전달
        return render_template(
            "dashboard.html",
            request=request, 
            requests=requests, 
            current_user={"name": session['user'], "role": session.get('role', 'employee')},
            monthly_overtime=monthly_overtime,
            remaining_compensatory_hours=remaining_compensatory_hours,
            pending_approvals=pending_approvals
        )
    except Exception as e:
        print(f"Dashboard error: {e}")
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>오류</title>
        </head>
        <body>
            <h1>대시보드 로딩 중 오류가 발생했습니다</h1>
            <p>오류 내용: {str(e)}</p>
            <p><a href="/">홈으로 돌아가기</a></p>
        </body>
        </html>
        """

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/?message=안전하게+로그아웃되었습니다.')

@app.route('/test')
def test():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <title>테스트 페이지</title>
    </head>
    <body>
        <h1>테스트 페이지</h1>
        <p>이 페이지는 인코딩 테스트를 위한 페이지입니다.</p>
        <p>한글이 제대로 표시되는지 확인합니다.</p>
        <p><a href="/">홈으로 돌아가기</a></p>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
