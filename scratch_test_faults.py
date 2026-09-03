from decimal import Decimal

from src.data.synthetic.config import GenerationConfig
from src.data.synthetic.runner import SyntheticEnvironment
from src.evaluation.engine import EvaluationEngine, prepare_evaluation_population
from src.evaluation.strategies import ReviveStrategy
from src.faults.injector import get_fault_injector
from src.faults.models import FaultType


def run_sim(fault_type: FaultType | None):
    print("\n=============================================")
    print(f"RUNNING SIMULATION WITH FAULT: {fault_type.name if fault_type else 'NONE'}")
    print("=============================================")
    injector = get_fault_injector()
    injector.clear()
    if fault_type:
        injector.configure(fault_type)

    config = GenerationConfig(seed=42, num_customers=100, num_months=1)
    env = SyntheticEnvironment(config)
    data = env.generate()
    population = prepare_evaluation_population(data)

    engine = EvaluationEngine()
    strategy = ReviveStrategy()

    results = engine.evaluate_strategy(strategy, population, eval_seed=42)

    total_interventions = 0
    executed = 0
    failed = 0
    success = 0
    gross_recovered = Decimal(0)
    net_recovered = Decimal(0)

    for r in results:
        if r.selected_action != "NO_ACTION" and r.guardrail_decision != "DENY":
            total_interventions += 1
            if r.executed:
                executed += 1
                if r.simulator_success:
                    success += 1
                else:
                    failed += 1
        gross_recovered += r.amount_recovered
        net_recovered += r.net_recovery

    print("Total customers: 100")
    print("Seed: 42")
    print("Strategy: REVIVE")
    print(f"Total Interventions: {total_interventions}")
    print(f"Executed: {executed}")
    print(f"Failed: {failed}")
    print(f"Success: {success}")
    print(f"Gross Recovered: Rs.{gross_recovered:,.2f}")
    print(f"Net Recovered: Rs.{net_recovered:,.2f}")


if __name__ == "__main__":
    run_sim(None)
    run_sim(FaultType.MODEL_UNAVAILABLE)
    run_sim(FaultType.GATEWAY_OUTAGE)
    run_sim(FaultType.POLICY_UNAVAILABLE)
