p = "app/services/auth_service.py"
s = open(p).read()
old1 = "SELECT role FROM employees WHERE name = :username"
new1 = "SELECT role, dept FROM employees WHERE name = :username"
s = s.replace(old1, new1)
old2 = "return User(name=username, role=db_user[0])"
new2 = "return User(name=username, role=db_user[0], dept=db_user[1])"
s = s.replace(old2, new2)
s = s.replace(old2, new2)
open(p, "w").write(s)
print("done")
