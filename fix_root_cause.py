filepath = r"src\agent\nodes\root_cause.py"
with open(filepath, encoding="utf-8") as f:
    content = f.read()

old_code = """            service = get_root_cause_service()
            prediction = service.diagnose(features=features, source_type=case.source_type)"""

new_code = """            service = get_root_cause_service()
            trigger_payment = next((p for p in payments if str(p.payment_id) == str(case.source_id)), None) if case.source_type == "payment" else None
            fc = trigger_payment.failure_code if trigger_payment else None
            fr = trigger_payment.failure_reason if trigger_payment else None
            prediction = service.diagnose(
                features=features, 
                source_type=case.source_type,
                failure_code=fc,
                failure_reason=fr
            )"""

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed root_cause.py")
else:
    print("Could not find target in root_cause.py")
