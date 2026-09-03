# Fix ui_service.py
svc_path = r"src\api\services\ui_service.py"
with open(svc_path, encoding="utf-8") as f:
    content = f.read()

old_blocks = """    # 6. Policy Blocks
    stmt_blocks = select(func.count(Intervention.intervention_id)).where(
        Intervention.policy_decision == "DENY"
    )
    policy_blocks = session.scalars(stmt_blocks).first() or 0"""

new_blocks = """    # 6. Policy Blocks
    from sqlalchemy import cast, String
    stmt_blocks = select(func.count(AuditEvent.event_id)).where(
        AuditEvent.event_type == "policy_check",
        cast(AuditEvent.metadata_, String).like('%"policy_decision": "DENY"%')
    )
    policy_blocks = session.scalars(stmt_blocks).first() or 0"""

if old_blocks in content:
    content = content.replace(old_blocks, new_blocks)
    with open(svc_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed ui_service.py")
else:
    print("Could not find target in ui_service.py")

# Fix app.py labels
app_path = r"frontend\app.py"
with open(app_path, encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    '<div class="kpi-title">Expected Recovery</div>',
    '<div class="kpi-title" title="Predicted net recovery for all active cases">Expected Recovery (Active)</div>',
)
content = content.replace(
    '<div class="kpi-title">Recovered Revenue</div>',
    '<div class="kpi-title" title="Actual revenue successfully realized from closed cases">Recovered (Realized)</div>',
)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed app.py")
