p = "app/api/request_routes.py"
s = open(p).read()
Q = chr(39)
old = "    # Check if the current user has permission to approve\n"
old += "    current_approver_result = db.execute(text(\"SELECT approver FROM requests WHERE id = :id\"), {\"id\": id}).fetchone()\n"
old += "    current_approver = current_approver_result[0]\n"
old += "\n"
old += "    if current_user.role not in ["
old += Q + "Admin" + Q + ", " + Q + "Approver" + Q + ", " + Q + "lead" + Q + "]:\n"
old += "        return RedirectResponse(url=\"/approve-list\", status_code=303)"
assert s.count(old) == 1, "old approve-gate not found"
new = "    # Check if the current user has permission to approve\n"
new += "    target_result = db.execute(text(\"SELECT e.dept, e.role FROM requests r JOIN employees e ON r.name = e.name WHERE r.id = :id\"), {\"id\":id}).fetchone()\n"
new += "    if target_result is None:\n"
new += "        return RedirectResponse(url=\"/approve-list\", status_code=303)\n"
new += "    target_dept, target_role = target_result\n"
new += "\n"
new += "    if not in_approval_scope(current_user.role, target_dept, target_role):\n"
new += "        return RedirectResponse(url=\"/approve-list\", status_code=303)"
s = s.replace(old, new, 1)
open(p, "w").write(s)
print("approve_request patched OK")
