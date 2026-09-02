# REVIVE — Autonomous Revenue Recovery & Intervention Engine

An AI-powered, confidence-aware revenue-recovery platform that detects revenue at risk,
diagnoses the cause, predicts the expected recovery value of candidate interventions,
selects the economically optimal permitted action, executes a bounded workflow,
measures the actual financial outcome, and records a complete audit trail.

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (required from Milestone 1 onward)

### Installation

```bash
# Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Install the project with dev dependencies
pip install -e ".[dev]"
```

### Configuration

Copy the example environment file and adjust as needed:

```bash
cp .env.example .env
```

### Running the Application

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Health Check

```bash
curl http://localhost:8000/health
```

### Running Tests

```bash
pytest
```

### Linting and Formatting

```bash
ruff check .
ruff format --check .
```

### Type Checking

```bash
mypy src/ tests/
```

## Project Structure

```
revive/
├── README.md
├── pyproject.toml
├── .env.example
├── config/
├── data/
├── notebooks/
├── src/
│   ├── api/
│   ├── data/
│   ├── features/
│   ├── models/
│   ├── decision/
│   ├── policy/
│   ├── agent/
│   ├── simulator/
│   ├── database/
│   └── audit/
├── frontend/
├── tests/
├── scripts/
└── artifacts/
```

## Specification Pack

See [`.agent/specs/`](.agent/specs/) for the complete specification pack.

## License

MIT
