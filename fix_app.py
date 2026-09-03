filepath = r"frontend/app.py"
with open(filepath, encoding="utf-8") as f:
    content = f.read()

old_code = """                {"Stage": "Actionable Cases", "Count": funnel["actionable_cases"]},
                {"Stage": "Approved Interventions", "Count": funnel["approved_interventions"]},
                {"Stage": "Successful Recoveries", "Count": funnel["successful_recoveries"]},"""

new_code = """                {"Stage": "Actionable Cases (Case-level)", "Count": funnel["actionable_cases"]},
                {"Stage": "Approved Actions (Intervention-level)", "Count": funnel["approved_interventions"]},
                {"Stage": "Successful Recoveries (Outcome-level)", "Count": funnel["successful_recoveries"]},"""

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated funnel UI labels")
else:
    print("Failed to find funnel UI labels")
