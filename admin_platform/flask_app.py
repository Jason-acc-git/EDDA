from flask import Flask, render_template, redirect, url_for, request, session
import os
import sqlite3
import hashlib

app = Flask(__name__, 
            template_folder='/Users/engineers/EDDA/admin_platform/app/templates',
            static_folder='/Users/engineers/EDDA/admin_platform/app/static')

app.secret_key = 'edda_secret_key'  # 세션을 위한 시크릿 키

# 데이터베이스 연결
def get_db_connection():
    conn = sqlite3.connect('/Users/engineers/EDDA/admin_platform/admin.db')
    conn.row_factory = sqlite3.Row
    return conn

# 홈 페이지
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

# 로그인 페이지
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        # POST 요청일 때만 폼 데이터를 처리합니다
        try:
            username = request.form['username']
            password = request.form['password']
            
            # 비밀번호 해싱 (SHA-256)
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                              (username, hashed_password)).fetchone()
            conn.close()
            
            if user:
                session['username'] = username
                session['user_id'] = user['id']
                session['is_admin'] = user['is_admin']
                
                if user['is_admin'] == 1:
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                error = '잘못된 사용자 이름 또는 비밀번호입니다.'
        except KeyError:
            error = '사용자 이름과 비밀번호를 입력하세요.'
    
    # GET 요청이거나 로그인 실패 시 로그인 페이지를 표시합니다
    return render_template('home.html', error=error)

# 대시보드 페이지
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', username=session['username'])

# 관리자 대시보드 페이지
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))
    
    return render_template('admin_dashboard.html', username=session['username'])

# 로그아웃
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    session.pop('is_admin', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)

