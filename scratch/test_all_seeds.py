import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Override the seeds
import scripts.evaluate_financials
from scripts.evaluate_financials import main

scripts.evaluate_financials.DEFAULT_SEEDS = [42, 43, 44, 45, 46]

if __name__ == "__main__":
    main()
