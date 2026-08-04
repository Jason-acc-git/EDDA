p = "app/api/admin_routes.py"
s = open(p, encoding="utf-8").read()
Q = chr(39)
old = "        pdf_approver_setting = db.execute(text(\"SELECT value FROM settings WHERE key = "
old += Q + "pdf_approver" + Q + "\")).fetchone()\n"
old += "        \n"
old += "        approver_name = None\n"
old += "        if pdf_approver_setting and pdf_approver_setting[0]:\n"
old += "            approver_name = pdf_approver_setting[0]\n"
old += "        else:\n"
old += "            approver_name = request_data.get("
old += Q + "approver" + Q + ")\n"
assert s.count(old) == 1, "old not found"
new = "        approver_name = request_data.get("
new += Q + "approver" + Q + ")\n"
new += "\n"
new += "        if not approver_name:\n"
new += "            pdf_approver_setting = db.execute(text(\"SELECT value FROM settings WHERE key = "
new += Q + "pdf_approver" + Q + "\")).fetchone()\n"
new += "            if pdf_approver_setting and pdf_approver_setting[0]:\n"
new += "                approver_name = pdf_approver_setting[0]\n"
s = s.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(s)
print("pdf approver patched OK")
