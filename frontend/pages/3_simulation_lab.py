import json
from decimal import Decimal

import streamlit as st

st.set_page_config(page_title="Simulation Lab", page_icon="🧪", layout="wide")

st.title("Simulation Lab")
st.markdown(
    "Run localized evaluations of recovery strategies against synthetic or historical populations."
)

st.markdown(
    """
    <style>
    /* Prevent truncation in metrics */
    [data-testid="stMetricValue"] {
        white-space: normal !important;
        word-break: break-word !important;
    }
    [data-testid="stMetricDelta"] {
        white-space: normal !important;
        word-break: break-word !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("Configuration")
    pop_size = st.number_input("Customer Count", min_value=10, max_value=5000, value=500, step=100)
    months = st.number_input("Months History", min_value=1, max_value=24, value=6)

    # Scenarios like RECESSION or HIGH_RISK are not natively supported by EvaluationEngine yet.
    scenario = "NORMAL"
    strategy_a = st.selectbox(
        "Compare Strategy A", ["NO_ACTION", "ALWAYS_RETRY", "GENERIC_REMINDER", "REVIVE"], index=1
    )
    strategy_b = st.selectbox(
        "Compare Strategy B", ["NO_ACTION", "ALWAYS_RETRY", "GENERIC_REMINDER", "REVIVE"], index=3
    )
    seed = st.number_input("PRNG Seed", value=42)

    if st.button("Run Simulation", type="primary", use_container_width=True):
        with st.spinner("Executing Simulation & Financial Evaluation..."):
            from src.data.synthetic.config import GenerationConfig
            from src.data.synthetic.runner import SyntheticEnvironment
            from src.evaluation.engine import EvaluationEngine, prepare_evaluation_population
            from src.evaluation.strategies import (
                AlwaysRetryStrategy,
                GenericReminderStrategy,
                NoActionStrategy,
                ReviveStrategy,
            )

            # Map selection to strategy class
            strategy_map = {
                "NO_ACTION": NoActionStrategy(),
                "ALWAYS_RETRY": AlwaysRetryStrategy(),
                "GENERIC_REMINDER": GenericReminderStrategy(),
                "REVIVE": ReviveStrategy(),
            }

            config = GenerationConfig(
                num_customers=int(pop_size), num_months=int(months), seed=int(seed)
            )
            env = SyntheticEnvironment(config)
            data = env.generate()
            population = prepare_evaluation_population(data)

            engine = EvaluationEngine()

            from src.evaluation.metrics import compute_financial_metrics, compute_safety_metrics

            # Run Strategy A
            strat_a = strategy_map[strategy_a]
            results_a = engine.evaluate_strategy(strat_a, population, eval_seed=int(seed))
            fin_a = compute_financial_metrics(results_a)
            safe_a = compute_safety_metrics(results_a)

            # Run Strategy B
            strat_b = strategy_map[strategy_b]
            results_b = engine.evaluate_strategy(strat_b, population, eval_seed=int(seed))
            fin_b = compute_financial_metrics(results_b)
            safe_b = compute_safety_metrics(results_b)

            # Store in session state to persist across reruns
            st.session_state["sim_results"] = {
                "fin_a": fin_a,
                "fin_b": fin_b,
                "safe_a": safe_a,
                "safe_b": safe_b,
                "seed": seed,
                "num_customers": int(pop_size),
                "num_months": int(months),
                "strategy_a": strategy_a,
                "strategy_b": strategy_b,
            }

            st.success("Simulation complete!")
            st.session_state["sim_run"] = True

with col2:
    st.subheader("Simulation Results")

    sim_data = st.session_state.get("sim_results")
    if not sim_data:
        st.info("Configure parameters and click 'Run Simulation' to see dynamic results.")
        st.markdown("---")
        st.write("Alternatively, view the static M11 Benchmark Reference below:")
        try:
            with open("artifacts/evaluations/m11_financial_report.json") as f:
                m11_data = json.load(f)
        except Exception:
            m11_data = None

        if m11_data:
            agg = m11_data.get("aggregated", {})
            strat_a_data = agg.get(strategy_a, {})
            strat_b_data = agg.get(strategy_b, {})

            if strat_a_data and strat_b_data:

                def extract_mean(data_dict, key):
                    return Decimal(data_dict.get(key, {}).get("mean", "0"))

                net_a = extract_mean(strat_a_data, "total_net_recovery")
                net_b = extract_mean(strat_b_data, "total_net_recovery")
                cost_a = extract_mean(strat_a_data, "total_intervention_cost")
                cost_b = extract_mean(strat_b_data, "total_intervention_cost")
                rate_a = extract_mean(strat_a_data, "recovery_rate")
                rate_b = extract_mean(strat_b_data, "recovery_rate")
                gross_a = extract_mean(strat_a_data, "total_amount_recovered")
                gross_b = extract_mean(strat_b_data, "total_amount_recovered")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric(label="Net Recovered (A)", value=f"₹{net_a:,.2f}")
                c2.metric(
                    label="Net Recovered (B)",
                    value=f"₹{net_b:,.2f}",
                    delta=f"{((net_b - net_a) / net_a * 100):.1f}%" if net_a > 0 else "N/A",
                )
                c3.metric(
                    label="Intervention Cost (A)", value=f"₹{cost_a:,.2f}"
                )
                
                cost_diff = cost_b - cost_a
                cost_delta_str = f"-₹{abs(cost_diff):,.2f}" if cost_diff < 0 else f"₹{cost_diff:,.2f}"
                
                c4.metric(
                    label="Intervention Cost (B)",
                    value=f"₹{cost_b:,.2f}",
                    delta=cost_delta_str,
                    delta_color="inverse",
                )
    else:
        st.info("Displaying dynamic simulation results based on your configuration.")
        st.markdown("### Simulation Configuration Used")
        st.markdown(f"""
        - **Scenario:** `NORMAL`
        - **Customers:** `{sim_data.get("num_customers", "N/A")}`
        - **History:** `{sim_data.get("num_months", "N/A")} months`
        - **Seed:** `{sim_data["seed"]}`
        - **Strategy A:** `{sim_data["strategy_a"]}`
        - **Strategy B:** `{sim_data["strategy_b"]}`
        """)
        st.markdown("---")

        fin_a = sim_data["fin_a"]
        fin_b = sim_data["fin_b"]
        sa = sim_data["strategy_a"]
        sb = sim_data["strategy_b"]

        net_a = fin_a.total_net_recovery
        net_b = fin_b.total_net_recovery
        cost_a = fin_a.total_intervention_cost
        cost_b = fin_b.total_intervention_cost
        rate_a = Decimal(str(fin_a.recovery_rate))
        rate_b = Decimal(str(fin_b.recovery_rate))
        gross_a = fin_a.total_amount_recovered
        gross_b = fin_b.total_amount_recovered

        st.markdown("### Head-to-Head Comparison")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(label=f"Net Recovered ({sa})", value=f"₹{net_a:,.2f}")
        c2.metric(
            label=f"Net Recovered ({sb})",
            value=f"₹{net_b:,.2f}",
            delta=f"{((net_b - net_a) / net_a * 100):.1f}%" if net_a > 0 else "N/A",
        )
        c3.metric(label=f"Intervention Cost ({sa})", value=f"₹{cost_a:,.2f}")
        
        cost_diff = cost_b - cost_a
        cost_delta_str = f"-₹{abs(cost_diff):,.2f}" if cost_diff < 0 else f"₹{cost_diff:,.2f}"
        
        c4.metric(
            label=f"Intervention Cost ({sb})",
            value=f"₹{cost_b:,.2f}",
            delta=cost_delta_str,
            delta_color="inverse",
        )

        c5, c6, c7, c8 = st.columns(4)
        c5.metric(label=f"Recovery Rate ({sa})", value=f"{rate_a * 100:.1f}%")
        c6.metric(
            label=f"Recovery Rate ({sb})",
            value=f"{rate_b * 100:.1f}%",
            delta=f"{(rate_b - rate_a) * 100:.1f} pts",
        )
        c7.metric(label=f"Gross Recovered ({sa})", value=f"₹{gross_a:,.2f}")
        
        gross_diff = gross_b - gross_a
        gross_delta_str = f"-₹{abs(gross_diff):,.2f}" if gross_diff < 0 else f"₹{gross_diff:,.2f}"
        
        c8.metric(
            label=f"Gross Recovered ({sb})", 
            value=f"₹{gross_b:,.2f}",
            delta=gross_delta_str
        )

        safe_a = sim_data.get("safe_a")
        safe_b = sim_data.get("safe_b")

        def format_violations(strat_name, safe_metrics):
            if strat_name == "REVIVE":
                return f"{safe_metrics.policy_violations} Policy Violations"
            else:
                return "N/A - Not measured by EvaluationEngine (Baselines bypass M8 by design)"

        viol_a = format_violations(sa, safe_a) if safe_a else "N/A"
        viol_b = format_violations(sb, safe_b) if safe_b else "N/A"

        st.markdown("### Policy Violations & Escalations")
        st.write(f"**{sa}:** {viol_a}")
        st.write(f"**{sb}:** {viol_b}")
        st.caption(
            "Evaluation engine dynamically measures policy checks for REVIVE. Baseline strategies are executed natively without M8 guardrail constraints."
        )
