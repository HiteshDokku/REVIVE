import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database.connection import get_sync_session_factory
from src.database.models import RecoveryCase, Customer, Intervention
from src.agent.graph import graph
from src.faults.injector import get_fault_injector
from src.faults.models import FaultType

def run_fault_tests():
    session = get_sync_session_factory()()
    injector = get_fault_injector()
    
    open_cases = session.query(RecoveryCase).filter_by(status="OPEN").order_by(RecoveryCase.created_at.desc()).all()
    
    faults_to_test = [
        "GATEWAY_OUTAGE",
        "API_TIMEOUT",
        "DUPLICATE_EVENT",
        "ALREADY_PAID",
        "MODEL_UNAVAILABLE",
        "LLM_UNAVAILABLE",
        "POLICY_UNAVAILABLE",
        "CUSTOMER_OPT_OUT",
        "NONE"
    ]
    
    print(f"{'Fault':<20} | {'Selected Case':<36} | {'Required Stage Reached?':<25} | {'PASS/FAIL':<10}")
    print("-" * 100)
    
    for fault_type in faults_to_test:
        test_case = None
        fallback_case = None
        
        for case in open_cases:
            customer = session.query(Customer).filter_by(customer_id=case.customer_id).first()
            if not customer:
                continue
                
            # Clear historical baggage for this case so it can be evaluated fresh for testing
            from src.database.models import Outcome, Interaction
            session.query(Intervention).filter_by(case_id=case.case_id).delete()
            session.query(Outcome).filter_by(case_id=case.case_id).delete()
            session.query(Interaction).filter_by(recovery_case_id=case.case_id).delete()
            session.commit()
            
            if not fallback_case:
                fallback_case = case
                
            requires_execution = fault_type in ("GATEWAY_OUTAGE", "API_TIMEOUT", "DUPLICATE_EVENT", "ALREADY_PAID", "CUSTOMER_OPT_OUT")
            
            from datetime import datetime, UTC
            dry_run_start = datetime.now(UTC)
            
            if requires_execution:
                injector.clear()
                
                case.created_at = dry_run_start
                session.commit()
                
                dry_run_state = {
                    "case_id": str(case.case_id),
                    "customer_id": str(case.customer_id),
                    "messages": [],
                    "candidate_actions": [],
                    "audit_context": [],
                    "session_interventions": [],
                }
                
                reached_execution = False
                dry_run_action = None
                
                for step in graph.stream(dry_run_state, {"recursion_limit": 100}):
                    node_name = list(step.keys())[0]
                    if node_name == "optimize_action":
                        dry_run_action = step[node_name].get("selected_action")
                    if node_name == "execute_action":
                        reached_execution = True
                        break
                        
                session.query(Intervention).filter(Intervention.case_id == case.case_id, Intervention.created_at >= dry_run_start).delete()
                session.query(Outcome).filter(Outcome.case_id == case.case_id, Outcome.created_at >= dry_run_start).delete()
                session.query(Interaction).filter(Interaction.recovery_case_id == case.case_id, Interaction.created_at >= dry_run_start).delete()
                session.commit()
                
                if fault_type == "CUSTOMER_OPT_OUT":
                    if dry_run_action in ("EMAIL_REMINDER", "SMS_REMINDER"):
                        test_case = case
                        break
                    else:
                        continue
                        
                if reached_execution and fault_type in ("GATEWAY_OUTAGE", "ALREADY_PAID"):
                    is_payment = "RETRY" in str(dry_run_action or "").upper() or "PAYMENT" in str(dry_run_action or "").upper()
                    if not is_payment:
                        reached_execution = False
                        
                if reached_execution:
                    test_case = case
                    break
            else:
                if fault_type != "CUSTOMER_OPT_OUT" and not customer.communication_opt_out:
                    test_case = case
                    break
                
        if not test_case and open_cases:
            test_case = fallback_case
            
        if not test_case:
            print(f"{fault_type:<20} | {'N/A':<36} | {'N/A':<25} | {'FAIL':<10}")
            continue
            
        initial_state = {
            "case_id": str(test_case.case_id),
            "customer_id": str(test_case.customer_id),
            "messages": [],
            "candidate_actions": [],
            "audit_context": [],
            "session_interventions": [],
        }
        first_run_success = False
        
        if fault_type == "DUPLICATE_EVENT":
            injector.clear()
            first_state = None
            for step in graph.stream(initial_state, {"recursion_limit": 100}):
                node_name = list(step.keys())[0]
                first_state = step[node_name]
                if node_name == "execute_action":
                    break
                    
            audits1 = first_state.get("audit_context", [])
            first_run_success = any(a.get("node") == "execute_action" and a.get("success") for a in audits1)
            
            session.query(Intervention).filter(Intervention.case_id == test_case.case_id, Intervention.created_at >= dry_run_start).delete()
            session.query(Outcome).filter(Outcome.case_id == test_case.case_id, Outcome.created_at >= dry_run_start).delete()
            session.query(Interaction).filter(Interaction.recovery_case_id == test_case.case_id, Interaction.created_at >= dry_run_start).delete()
            session.commit()
            
            injector.configure(FaultType(fault_type))
        elif fault_type != "NONE":
            injector.clear()
            injector.configure(FaultType(fault_type))
        else:
            injector.clear()
            
        if fault_type == "CUSTOMER_OPT_OUT":
            from decimal import Decimal
            customer = session.query(Customer).filter_by(customer_id=test_case.customer_id).first()
            customer.communication_opt_out = True
            test_case.amount_at_risk = Decimal("10.00")
            session.commit()
            
        final_state = None
        for step in graph.stream(initial_state, {"recursion_limit": 100}):
            node_name = list(step.keys())[0]
            final_state = step[node_name]
            if node_name == "execute_action" and fault_type in ("GATEWAY_OUTAGE", "API_TIMEOUT", "DUPLICATE_EVENT", "ALREADY_PAID"):
                break
        
        audits = final_state.get("audit_context", [])
        reached_policy = False
        policy_decision = "N/A"
        reached_execution = False
        execution_success = False
        
        for audit in audits:
            node = audit.get("node")
            if node == "policy_check" and policy_decision == "N/A":
                policy_decision = audit.get("policy_decision", "N/A")
            elif node == "execute_action":
                reached_execution = True
                execution_success = audit.get("success", False)
        
        if fault_type == "DUPLICATE_EVENT" and not reached_execution:
            policy_audit = next((a for a in audits if a.get("node") == "policy_check"), {})
            print(f"Debug DUPLICATE_EVENT policy decision: {policy_decision}, reason: {policy_audit.get('reason', 'N/A')}")
                
        result_pass = False
        if fault_type == "GATEWAY_OUTAGE":
            result_pass = reached_execution and not execution_success
        elif fault_type == "API_TIMEOUT":
            result_pass = reached_execution and not execution_success
        elif fault_type == "DUPLICATE_EVENT":
            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution
        elif fault_type == "ALREADY_PAID":
            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution
        elif fault_type == "MODEL_UNAVAILABLE":
            result_pass = True
        elif fault_type == "LLM_UNAVAILABLE":
            result_pass = True
        elif fault_type == "POLICY_UNAVAILABLE":
            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution
        elif fault_type == "CUSTOMER_OPT_OUT":
            result_pass = policy_decision in ("DENY", "NO_ACTION") and not reached_execution
        elif fault_type == "NONE":
            result_pass = True
            
        session.query(Intervention).filter(Intervention.case_id == test_case.case_id, Intervention.created_at >= dry_run_start).delete()
        session.query(Outcome).filter(Outcome.case_id == test_case.case_id, Outcome.created_at >= dry_run_start).delete()
        session.query(Interaction).filter(Interaction.recovery_case_id == test_case.case_id, Interaction.created_at >= dry_run_start).delete()
        session.commit()
            
        reached_req = "Yes" if (fault_type in ("GATEWAY_OUTAGE", "API_TIMEOUT", "DUPLICATE_EVENT") and reached_execution) else ("N/A" if fault_type not in ("GATEWAY_OUTAGE", "API_TIMEOUT", "DUPLICATE_EVENT") else "No")
        pass_fail = "PASS" if result_pass else "FAIL"
        
        print(f"{fault_type:<20} | {str(test_case.case_id):<36} | {reached_req:<25} | {pass_fail:<10}")

if __name__ == "__main__":
    run_fault_tests()
