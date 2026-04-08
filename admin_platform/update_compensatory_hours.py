
import sqlite3
import json

def update_compensatory_hours():
    conn = sqlite3.connect('admin.db')
    cursor = conn.cursor()

    cursor.execute("SELECT id, content FROM requests WHERE type = '시간외 근무' AND json_extract(content, '$.compensation') = '대체휴가'")
    requests = cursor.fetchall()

    for req in requests:
        req_id, content_json = req
        content = json.loads(content_json)

        work_hours_weekday = content.get('work_hours_weekday', 0)
        work_hours_holiday = content.get('work_hours_holiday', 0)
        total_hours = work_hours_weekday + work_hours_holiday

        content['calculated_compensatory_hours'] = total_hours

        cursor.execute("UPDATE requests SET content = ? WHERE id = ?", (json.dumps(content), req_id))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_compensatory_hours()
