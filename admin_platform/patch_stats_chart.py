p1 = "app/api/admin_routes.py"
s1 = open(p1, encoding="utf-8").read()

old_fn = '''@router.get("/api/stats/overtime-hours")
def get_overtime_hours(
    period: str = Query("monthly", enum=["monthly", "yearly"]),
    month: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Approver", "Lead", "Manager"], use_cache=False))
):
    employees_result = db.execute(text("SELECT name FROM employees WHERE name NOT IN ('admin', 'lead')")).fetchall()
    employees = [row[0] for row in employees_result]

    labels = []
    data = []
    today = datetime.today()

    for emp_name in employees:
        labels.append(emp_name)
        total_hours = 0

        if period == "monthly":
            if month:
                target_month_dt = datetime.strptime(month, "%Y-%m")
            else:
                target_month_dt = today

            end_date = (target_month_dt.replace(day=15)).strftime("%Y-%m-%d")
            start_date = (target_month_dt.replace(day=16) - relativedelta(months=1)).strftime("%Y-%m-%d")

        else: # yearly
            start_date = today.replace(month=1, day=1).strftime("%Y-%m-%d")
            end_date = today.replace(month=12, day=31).strftime("%Y-%m-%d")

        requests_result = db.execute(text("SELECT content FROM requests WHERE name = :name AND type = '시간외 근무' AND (status LIKE '%대기' OR status = '재신청' OR status = 'approved') AND json_extract(content, '$.work_date') BETWEEN :start_date AND :end_date"), {"name": emp_name, "start_date": start_date, "end_date": end_date}).fetchall()
        for req in requests_result:
            content = json.loads(req[0])
            total_hours += content.get('work_hours_weekday', 0) + content.get('work_hours_holiday', 0)

        data.append(total_hours)

    return JSONResponse(content={"labels": labels, "data": data})'''

assert s1.count(old_fn) == 1, "old_fn not found in admin_routes.py"

new_fn = '''@router.get("/api/stats/overtime-hours")
def get_overtime_hours(
    period: str = Query("monthly", enum=["monthly", "yearly"]),
    month: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Approver", "Lead", "Manager"], use_cache=False))
):
    employees_result = db.execute(text("SELECT name FROM employees WHERE name NOT IN ('admin', 'lead')")).fetchall()
    employees = [row[0] for row in employees_result]

    labels = []
    data_allowance = []
    data_leave = []
    today = datetime.today()

    for emp_name in employees:
        labels.append(emp_name)
        allowance_hours = 0
        leave_hours = 0

        if period == "monthly":
            if month:
                target_month_dt = datetime.strptime(month, "%Y-%m")
            else:
                target_month_dt = today

            end_date = (target_month_dt.replace(day=15)).strftime("%Y-%m-%d")
            start_date = (target_month_dt.replace(day=16) - relativedelta(months=1)).strftime("%Y-%m-%d")

        else: # yearly
            start_date = today.replace(month=1, day=1).strftime("%Y-%m-%d")
            end_date = today.replace(month=12, day=31).strftime("%Y-%m-%d")

        requests_result = db.execute(text("SELECT content FROM requests WHERE name = :name AND type = '시간외 근무' AND (status LIKE '%대기' OR status = '재신청' OR status = 'approved') AND json_extract(content, '$.work_date') BETWEEN :start_date AND :end_date"), {"name": emp_name, "start_date": start_date, "end_date": end_date}).fetchall()
        for req in requests_result:
            content = json.loads(req[0])
            hours = content.get('work_hours_weekday', 0) + content.get('work_hours_holiday', 0)
            if content.get('compensation') == '대체휴가':
                leave_hours += hours
            else:
                allowance_hours += hours

        data_allowance.append(allowance_hours)
        data_leave.append(leave_hours)

    return JSONResponse(content={"labels": labels, "data_allowance": data_allowance, "data_leave": data_leave})'''

s1 = s1.replace(old_fn, new_fn, 1)
open(p1, "w", encoding="utf-8").write(s1)
print("admin_routes.py stats function patched OK")

p2 = "app/templates/stats.html"
s2 = open(p2, encoding="utf-8").read()

old_js = '''                .then(data => {
                    const ctx = document.getElementById('overtimeChart').getContext('2d');
                    if (overtimeChart) {
                        overtimeChart.destroy();
                    }
                    overtimeChart = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: data.labels,
                            datasets: [{
                                label: `시간외 근무 시간 (${period === 'monthly' ? (month ? `${month.split('-')[0]}년 ${parseInt(month.split('-')[1])}월` : '월별') : '연간'})`,
                                data: data.data,
                                backgroundColor: '#A9D0F5',
                                borderColor: '#A9D0F5',
                                borderWidth: 1
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: {
                                    display: true
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    ticks: {
                                        stepSize: 1
                                    }
                                }
                            }
                        }
                    });
                })'''

assert s2.count(old_js) == 1, "old_js not found in stats.html"

new_js = '''                .then(data => {
                    const ctx = document.getElementById('overtimeChart').getContext('2d');
                    if (overtimeChart) {
                        overtimeChart.destroy();
                    }
                    overtimeChart = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: data.labels,
                            datasets: [
                                {
                                    label: '수당지급',
                                    data: data.data_allowance,
                                    backgroundColor: '#A9D0F5',
                                    borderColor: '#A9D0F5',
                                    borderWidth: 1
                                },
                                {
                                    label: '대체휴가',
                                    data: data.data_leave,
                                    backgroundColor: '#F5B7A9',
                                    borderColor: '#F5B7A9',
                                    borderWidth: 1
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: {
                                    display: true
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    ticks: {
                                        stepSize: 1
                                    }
                                }
                            }
                        }
                    });
                })'''

s2 = s2.replace(old_js, new_js, 1)
open(p2, "w", encoding="utf-8").write(s2)
print("stats.html chart patched OK")
