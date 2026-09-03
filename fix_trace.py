filepath = r"frontend/pages/2_decision_trace.py"
with open(filepath, encoding="utf-8") as f:
    content = f.read()
old_code = """    stages["outcome"] = {
        "recovered": case.get("expected_recovery") if case.get("status") == "CLOSED" else 0.0,
        "status": case.get("status", "PENDING"),
    }"""
new_code = """    stages["outcome"] = {
        "recovered": case.get("amount_recovered") if case.get("status") == "RECOVERED" else 0.0,
        "status": case.get("status", "PENDING"),
    }"""
content = content.replace(old_code, new_code)
with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed decision_trace.py")
