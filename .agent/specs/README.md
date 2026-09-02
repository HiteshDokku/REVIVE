# REVIVE Antigravity Specification Pack

This directory is the source-of-truth specification pack for the REVIVE project.

## Files

- [AGENTS.md](./AGENTS.md) — mandatory instructions for Google Antigravity
- [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) — problem, goals, value proposition, success metrics
- [ARCHITECTURE.md](./ARCHITECTURE.md) — system topology and component boundaries
- [TECHNICAL_SPEC.md](./TECHNICAL_SPEC.md) — implementation contracts and APIs
- [SCHEMA.md](./SCHEMA.md) — database schema and data dictionary
- [DATA_GENERATION.md](./DATA_GENERATION.md) — synthetic environment specification
- [ML_SPEC.md](./ML_SPEC.md) — model and evaluation specification
- [AGENT_SPEC.md](./AGENT_SPEC.md) — LangGraph agent design
- [POLICY.md](./POLICY.md) — guardrails and deterministic operating rules
- [EVALUATION.md](./EVALUATION.md) — financial, ML, safety, and robustness evaluation
- [UI_SPEC.md](./UI_SPEC.md) — Streamlit control-tower specification
- [ROADMAP.md](./ROADMAP.md) — milestone-by-milestone execution plan

## Execution Rule

Antigravity MUST work one milestone at a time.

After completing each milestone it MUST:

1. Stop implementation.
2. Run the complete relevant test suite.
3. Run linting.
4. Run type checking when applicable.
5. Run integration or end-to-end checks relevant to the milestone.
6. Verify the milestone Definition of Done.
7. Report exactly what changed, what passed, what failed, and any blockers.
8. WAIT for the next user instruction before starting another milestone.

Antigravity MUST NOT autonomously continue from one milestone to the next.

See [AGENTS.md](./AGENTS.md) and [ROADMAP.md](./ROADMAP.md).
