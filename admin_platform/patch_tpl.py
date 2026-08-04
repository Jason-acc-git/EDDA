p = "app/templates/approve_list.html"
s = open(p, encoding="utf-8").read()
Q = chr(39)
SP = " " * 28
old_a = SP + "{% if (current_user.role == \"Approver\" or current_user.role == "
old_a += Q + "Admin" + Q + ") and r.status != "
old_a += Q + "approved" + Q + " and r.status != "
old_a += Q + "rejected" + Q + " %}"
assert s.count(old_a) == 1, "old_a not found"
new_a = SP + "{% if current_user.role in [\"Approver\", \"Admin\", \"Lead\"] and r.status != "
new_a += Q + "approved" + Q + " and r.status != "
new_a += Q + "rejected" + Q + " %}"
s = s.replace(old_a, new_a, 1)
old_b = SP + "{% elif r.status == "
old_b += Q + "approved" + Q + " and current_user.role in ["
old_b += Q + "Admin" + Q + ", " + Q + "Manager" + Q + ", " + Q + "Lead" + Q + "] %}"
assert s.count(old_b) == 1, "old_b not found"
new_b = SP + "{% elif r.status == "
new_b += Q + "approved" + Q + " and current_user.role in ["
new_b += Q + "Admin" + Q + ", " + Q + "Manager" + Q + ", " + Q + "Lead" + Q + ", " + Q + "Approver" + Q + "]%}"
s = s.replace(old_b, new_b, 1)
open(p, "w", encoding="utf-8").write(s)
print("template patched OK")
