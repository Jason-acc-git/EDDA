import sqlite3

def reset_requests_data():
    """직원 정보 관련 데이터를 제외한 모든 데이터를 리셋합니다."""
    
    conn = sqlite3.connect("admin.db")
    cur = conn.cursor()
    
    # requests 테이블의 모든 데이터 삭제
    cur.execute("DELETE FROM requests")
    
    # 변경사항 저장
    conn.commit()
    conn.close()
    
    print("신청 내역 데이터가 성공적으로 리셋되었습니다.")

if __name__ == "__main__":
    # 사용자 확인 없이 바로 실행
    reset_requests_data()